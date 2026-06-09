# Copyright 2026 Paweł Zuzelski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

load("@rules_pkg//pkg:tar.bzl", "pkg_tar")
load("@rules_pkg//pkg:deb.bzl", "pkg_deb")

genrule(
    name = "copy_server_jar",
    srcs = ["//java/ch/execve/elm/serving:serving_server_deploy.jar"],
    outs = ["elm-server.jar"],
    cmd = "cp $< $@",
)

genrule(
    name = "copy_client_binary",
    srcs = ["//client:client"],
    outs = ["elm-client"],
    cmd = "cp $< $@",
)

pkg_tar(
    name = "server_jar",
    srcs = [":copy_server_jar"],
    package_dir = "/usr/share/elm",
)

pkg_tar(
    name = "client_binary",
    srcs = [":copy_client_binary"],
    package_dir = "/usr/bin",
    mode = "0755",
)

pkg_tar(
    name = "systemd_service",
    srcs = ["elm-server.service"],
    package_dir = "/lib/systemd/system",
)

pkg_tar(
    name = "debian-data",
    extension = "tar.gz",
    deps = [
        ":server_jar",
        ":client_binary",
        ":systemd_service",
    ],
)

pkg_deb(
    name = "elm_deb",
    package = "elm-server",
    version = "1.0.0",
    architecture = "arm64",
    maintainer = "Paweł Zuzelski <pawelz@execve.ch>",
    description = "Elm Spam Classification Server and Client",
    depends = ["openjdk-25-jre-headless"],
    data = ":debian-data",
    postinst = "postinst",
    prerm = "prerm",
)
