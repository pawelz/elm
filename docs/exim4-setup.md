# Production Deployment & Exim4 Integration on Raspbian (Debian)

This guide provides step-by-step instructions to deploy the `ElmServer` spam classifier as a systemd service, configure the C client, and wire it up inside **Exim4** and **Maildrop** on a Raspbian/Debian system.

---

## 1. Install Java 21 on Raspbian
`ElmServer` requires Java 21. Install the headless runtime package via APT:
```bash
sudo apt update
sudo apt install openjdk-21-jre-headless
```

---

## 2. Package and Install the ElmServer Daemon
On your build machine, package the Java application into a single, self-contained executable deployable JAR:
```bash
bazel build //java/ch/execve/elm/serving:serving_server_deploy.jar
```

Copy the generated JAR to `/usr/local/share/elm/` on your Raspbian mail server:
```bash
sudo mkdir -p /usr/local/share/elm
sudo cp bazel-bin/java/ch/execve/elm/serving/serving_server_deploy.jar /usr/local/share/elm/elm-server.jar
```

---

## 3. Configure the systemd Service
Create the service unit file to manage the daemon process:
```bash
sudo nano /etc/systemd/system/elm-server.service
```

Paste the following configuration:
```ini
[Unit]
Description=Elm Spam Classification Server
After=network.target

[Service]
Type=simple
User=mail
Group=mail
ExecStart=/usr/bin/java -jar /usr/local/share/elm/elm-server.jar --socket /run/elm/elm.sock
Restart=always
RestartSec=5

# Automates directory creation and permission management on socket directories
RuntimeDirectory=elm
RuntimeDirectoryMode=0775

[Install]
WantedBy=multi-user.target
```

Reload and enable the service to start automatically on boot:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now elm-server
```

Check the status of your daemon:
```bash
sudo systemctl status elm-server
```

---

## 4. Secure Socket Permissions
On Debian-based systems like Raspbian, Exim4 typically runs as the `Debian-exim` system user. To ensure that Exim's pipeline can write to our UNIX domain socket owned by the `mail` group, add the `Debian-exim` user to the `mail` group:

```bash
sudo usermod -aG mail Debian-exim
```
*(You may need to restart the `exim4` service for this group membership change to take effect).*

---

## 5. Compile and Install the C Client
On the Raspbian mail server, compile the native client and move it to a globally accessible path:

```bash
# Build the client
bazel build //client:client

# Install to /usr/local/bin
sudo cp bazel-bin/client/client /usr/local/bin/elm-client
```

Verify that the client can connect and talk to the daemon in filter mode:
```bash
echo "Subject: replica watches" | /usr/local/bin/elm-client --socket /run/elm/elm.sock --filter
```
You should see output similar to:
```rfc822
X-Spam-Status: Yes, score=0.9850, threshold=0.5000
X-Spam-Score: 0.9850
X-Spam-Threshold: 0.5000
Subject: replica watches
```

---

## 6. Configure Exim4 (via transport_filter)
Debian and Raspbian organize Exim4 configuration in two ways: **split configuration** (multiple files under `/etc/exim4/conf.d/`) or **unsplit configuration** (one template `/etc/exim4/exim4.conf.template`).

To find out which configuration style you use, run:
```bash
grep dc_use_split_config /etc/exim4/update-exim4.conf.conf
```

### Path A: Split Configuration
Locate the file defining your Maildrop/Procmail transport. This is typically located at:
`/etc/exim4/conf.d/transport/30_exim4-config_procmail_pipe`

Open the file and add the `transport_filter` line directly to the transport definition:
```exim
procmail_pipe:
  driver = pipe
  command = /usr/bin/maildrop -d $local_part
  # Add the client filter line here:
  transport_filter = /usr/local/bin/elm-client --socket /run/elm/elm.sock --filter --threshold 0.50
  return_path_add
  delivery_date_add
  envelope_to_add
  check_string = "From "
  escape_string = ">From "
  umask = 077
  user = $local_part
  group = mail
```

### Path B: Unsplit Configuration
If you use the single-template setup, open the file `/etc/exim4/exim4.conf.template` and search for `procmail_pipe:` or `maildrop_pipe:`. Add the `transport_filter` line there:
```exim
transport_filter = /usr/local/bin/elm-client --socket /run/elm/elm.sock --filter --threshold 0.50
```

### Apply Changes to Exim4
On Raspbian/Debian, you **must regenerate the active configuration** and restart the service for changes to take effect:
```bash
# Regenerate Exim4 configuration
sudo update-exim4.conf

# Restart the Exim4 service
sudo systemctl restart exim4
```

---

## 7. Set Up Maildrop Folders

### Step 1: Shadow Mode (Safe Dry-Run Testing)
To collect real statistics and verify accuracy without moving any mail, leave your `~/.mailfilter` file unmodified. 

All emails delivered to your inbox will now have headers added at the very top:
```rfc822
X-Spam-Status: No, score=0.0150, threshold=0.5000
X-Spam-Score: 0.0150
X-Spam-Threshold: 0.5000
```
Open a few emails in your mail client to verify that the classification headers are appearing correctly!

### Step 2: Production Mode (Automated Spam Sorting)
Once you are confident in the classification scores, open your `~/.mailfilter` and add a rule to filter emails into your Spam Maildir:

```maildrop
# Check if the header injected by Exim4's transport_filter marks the mail as spam
if (/^X-Spam-Status: Yes/:h)
{
    to "Maildir/.Spam/"
}
```

This setup keeps your user-space `.mailfilter` incredibly clean and fast, while the system service manages the heavy lifting!
