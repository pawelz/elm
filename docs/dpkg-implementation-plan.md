# Implementation Plan - Debian Packaging for ElmServer and C Client

We want to build a Debian package (`.deb`) for the `ElmServer` spam classifier using Bazel. This will package the Java 25 backend service, the native C client, and the systemd service configurations into a single, clean `.deb` package that can be easily installed on Raspbian / Debian.

## User Review Required

We are designing this package using Bazel's `@rules_pkg` package. Since `rules_pkg` is cross-platform, you can run the build on **either** macOS or Raspbian:
- **Natively on Raspbian (Recommended):** If you clone and run `bazel build //pkg:elm_deb` on Raspbian, Bazel will natively compile the C client for your Raspbian ARM architecture, and the package will contain the correct native binary.
- **On macOS (Cross-Platform):** You can build the `.deb` file on macOS. However, because cross-compiling C code to Linux ARM on macOS requires configuring complex cross-compiler toolchains, compiling natively on Raspbian is far simpler and more reliable.

> [!IMPORTANT]
> The Debian package target will be configured for `arm64` by default (which matches standard 64-bit Raspberry Pi OS). If you are running 32-bit Raspbian (`armhf`), you can easily change the architecture attribute in the build file or we can make it a configurable setting.

## Proposed Changes

### Build Configuration

#### [MODIFY] [MODULE.bazel](file:///Users/pawelz/git/elm/MODULE.bazel)
- Add the `rules_pkg` dependency so we can use package definition rules.
```python
bazel_dep(name = "rules_pkg", version = "1.0.1")
```

---

### Debian Packaging files

#### [NEW] [BUILD](file:///Users/pawelz/git/elm/pkg/BUILD)
Create a Bazel build file under a new `pkg` package. It will:
1. Define genrules to copy the built targets (`serving_server_deploy.jar` and `client` binary) to clean filenames (`elm-server.jar` and `elm-client`).
2. Define `pkg_tar` rules for:
   - `/usr/share/elm/elm-server.jar`
   - `/usr/bin/elm-client`
   - `/lib/systemd/system/elm-server.service`
3. Define an aggregator `pkg_tar` to merge these components.
4. Define `pkg_deb` to produce `elm-server_1.0.0_arm64.deb`, with:
   - Maintainer scripts (`postinst`, `prerm`)
   - Package metadata (maintainer, package name, version, architecture, description)
   - Dependencies: `openjdk-25-jre-headless`

#### [NEW] [elm-server.service](file:///Users/pawelz/git/elm/pkg/elm-server.service)
Create the systemd service template that uses standard Debian paths:
- Java jar located at `/usr/share/elm/elm-server.jar`
- Socket located at `/run/elm/elm.sock`

#### [NEW] [postinst](file:///Users/pawelz/git/elm/pkg/postinst)
The Debian post-installation script to:
1. Reload systemd daemon configurations.
2. Enable and start the `elm-server` service.
3. Automatically add the `Debian-exim` user to the `mail` group so Exim4 can access the socket.

#### [NEW] [prerm](file:///Users/pawelz/git/elm/pkg/prerm)
The Debian pre-removal script to stop and disable the `elm-server` service before uninstalling the package.

---

### Documentation

#### [MODIFY] [exim4-setup.md](file:///Users/pawelz/git/elm/docs/exim4-setup.md)
Update the setup documentation to explain the modern, unified Debian package installation:
- Building the package via Bazel on Raspbian: `bazel build //pkg:elm_deb`
- Installing the package: `sudo dpkg -i bazel-bin/pkg/elm_deb.deb`
- This replaces Steps 1, 2, 3, 4, and 5 with a single command!

## Verification Plan

### Automated Tests
- Run `bazel build //pkg:elm_deb` on the local machine (macOS) to verify that Bazel resolves `rules_pkg`, correctly copy-maps the outputs, generates the tarballs, and outputs a `.deb` package file without errors.

### Manual Verification
- Verify the contents of the generated `.deb` file on macOS by unpacking the archive using standard tools (e.g. `ar` or `tar`) to verify the file layout and permissions.
- Provide instructions for the user to copy the `.deb` file or build it on their Raspbian system, run `sudo dpkg -i`, and check that the service starts and group permissions are updated.
