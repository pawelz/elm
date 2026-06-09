# Production Deployment & Exim4 Integration on Raspbian (Debian)

This guide provides step-by-step instructions to deploy the `ElmServer` spam classifier as a systemd service, configure the C client, and wire it up inside **Exim4** and **Maildrop** on a Raspbian/Debian system.

We provide a Bazel target to build a standard Debian package (`.deb`) which automates the setup, installs dependencies (like Java 25 headless), registers the systemd service, installs the compiled native client, and configures group memberships automatically.

---

## 1. Build the Debian Package

To ensure the C client binary is compiled for your Raspberry Pi's CPU architecture, build the package directly on your Raspbian system:

```bash
# Clone the repository and run the build
bazel build //pkg:elm_deb
```

> [!TIP]
> If you build on a macOS build machine, the resulting `.deb` package will compile successfully and package the Java service and systemd configurations perfectly. However, the C client contained within will be a Mac binary. Build on Raspbian to ensure native ARM compilation.

---

## 2. Install the Package

Install the generated `.deb` package using `apt` so that dependencies (such as `openjdk-25-jre-headless`) are automatically resolved and installed:

```bash
sudo apt update
sudo apt install ./bazel-bin/pkg/elm-server_1.0.0_arm64.deb
```

*(This command installs the server JAR, registers and starts the systemd service, installs the native C client, and adds the `Debian-exim` user to the `mail` group automatically).*

---

## 3. Verify the Installation

Ensure the server is running and active:

```bash
sudo systemctl status elm-server
```

Verify that the client can connect and talk to the daemon in filter mode:
```bash
echo "Subject: replica watches" | /usr/bin/elm-client --socket /run/elm/elm.sock --filter
```
You should see output similar to:
```rfc822
X-Spam-Status: Yes, score=0.9850, threshold=0.5000
X-Spam-Score: 0.9850
X-Spam-Threshold: 0.5000
Subject: replica watches
```

---

## 4. Configure Exim4 (via transport_filter)
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
  transport_filter = /usr/bin/elm-client --socket /run/elm/elm.sock --filter --threshold 0.50
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
transport_filter = /usr/bin/elm-client --socket /run/elm/elm.sock --filter --threshold 0.50
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
