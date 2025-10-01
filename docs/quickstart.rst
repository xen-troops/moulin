Quickstart
==========

This document provides a few examples to give you the feel.

YAML format
-----------

YAML (yet-another-markup-language) is a quite simple tree-like file
format that can be easily read by humans and machines. If you are not
familiar with it, you can take a look at the `official specification
<https://yaml.org/spec/1.2/spec.html#Preview>`_ or read any of
the multiple guides that are available on the Internet.

For most of this documentation, we assume that you can read and
understand YAML files.

Simple Android build
--------------------

There is an example of a minimal AOSP build:

.. code-block:: yaml

		desc: "Build Android 11 XenVM image for Renesas Rcar H3"
		components:
		  android:
		    sources:
		      - type: repo
		        url: https://github.com/xen-troops/android_manifest.git
		        rev: android-11-master
		        manifest: doma.xml
		        depth: 1
		        groups: all
		        dir: "."
		    builder:
		      type: android
		      env:
		        - "TARGET_BOARD_PLATFORM=r8a7795"
		      lunch_target: xenvm-userdebug
		      target_images:
		        - "out/xenvm/userdebug/boot.img"
		        - "out/xenvm/userdebug/system.img"

Let's discuss what's happening there. This project file consists of two
mandatory sections. :code:`desc` provides a description for the
build. In this case, it tells us that we will build a particular
variant of Android 11.

:code:`components` section is the central part of the file. It describes
only one component, which is :code:`android`, of course. Every
component consists of two main parts: :code:`sources` and
:code:`builder`.

:code:`sources` describe all code sources that should be fetched prior
to building. In this particular case, we have only one `repo
<https://gerrit.googlesource.com/git-repo>`_ - based source.

:code:`builder` section configures the actual build. In this example,
we are building Android, so it has Android-specific options like
:code:`lunch_target`.

If the code above is stored in file `android-vm.yaml`, you can issue
:code:`moulin android-vm.yaml`. This will create a `build.ninja` file in
the same directory. After that, just run `ninja` and it will use
`repo` to fetch the given manifest, synchronize sources, and start the
build.


Parameterized Yocto build
-------------------------

Now let's consider more complex example:

.. code-block:: yaml

		desc: "Xilinx BSP"

		variables:
		  MACHINE: "this will be overwritten by parameters"

		components:
		  xilinx-bsp:
		    sources:
		      - type: git
		        url: "git://git.yoctoproject.org/poky"
		        rev: gatesgarth
		      - type: git
		        url: "git://git.yoctoproject.org/meta-xilinx"
		        rev: gatesgarth
		    builder:
		      type: yocto
		      conf:
		        - [MACHINE, "%{MACHINE}"]
		      build_target: core-image-minimal
		      layers:
		        - "../meta-xilinx/meta-xilinx-bsp"
		        - "../meta-xilinx/meta-xilinx-standalone"
		        - "../meta-xilinx/meta-xilinx-contrib"
		      target_images:
		        - "tmp/deploy/images/%{MACHINE}/core-image-minimal-%{MACHINE}.tar.gz"
		        - "tmp/deploy/images/%{MACHINE}/zImage"
		        - "tmp/deploy/images/%{MACHINE}/boot.bin"

		parameters:
		  MACHINE:
		    desc: "Xilinx device for which we will build"
		    # Couple of machines are chosen at random just for demonstration purposes
		    zc702-zynq7:
		      default: true
		      overrides:
		        variables:
		          MACHINE: zc702-zynq7
		    zc706-zynq7:
		      overrides:
		        variables:
		          MACHINE: zc706-zynq7
		    qemu-zynq7:
		      overrides:
		        variables:
		          MACHINE: qemu-zynq7


This build file allows you to build the Xilinx BSP for one of the selected
devices(zc702-zynq7, zc706-zynq7, qemu-zynq7). Apart from the early
discussed :code:`desc` and :code:`components` sections, we can see two
new: :code:`variables` and :code:`parameters`. But let's take a look
at the component. In this case, we are fetching two `git`
repositories. Also, we are building a Yocto distribution now, and we have
a completely different builder with different options. You can see
familiar Yocto settings like a list of layers on the additional `local.conf`
entries. All those sections are described in detail in the reference manual.


:code:`variables` section describes variables. This is basically
strings that can be used in any other part of the file using
:code:`%{VARIABLE_NAME}` syntax. We are using :code:`%` symbol instead
of the more familiar :code:`$` sign to ensure that it will not clash with
`bitbake`'s or `make`'s variables. It is really annoying to escape
dollar signs in constructions like the following::

  conf:
    - [SSTATE_DIR, "${TOPDIR}/../common_data/sstate"]
    - [DL_DIR, "${TOPDIR}/../common_data/downloads"]

Please note that in this particular example topmost :code:`variables`
section can be omitted, because only one variable will be overwritten
by subsequent :code:`parameters`. But, generally, you can define
variables there. Also, one variable can refer to another:

.. code-block:: yaml

		variables:
		  A: "justA"
		  B: "%{A}_%{A}" # will be expanded to "justA_justA"

:code:`%` itself can be escaped by doubling it:

.. code-block:: yaml

		variables:
		  A: "justA"
		  B: "%%{A}_%%{A}" # will be expanded to "%{A}_%{A}"

:code:`parameters` section provides means to parameterize your
build. If you have such a section in your build file, you can get help
using `moulin` itself::

  $ moulin xilinx-bsp.yaml --help-config
  usage: moulin.py xilinx-bsp.yaml [--MACHINE {zc702-zynq7,zc706-zynq7,qemu-zynq7}]

  Config file description: Xilinx BSP

  optional arguments:
      --MACHINE {zc702-zynq7,zc706-zynq7,qemu-zynq7}
                            Xilinx device for which we will build

:code:`parameters` section consists of one or more parameters, and each
parameter can have a number of predefined values, one of which must
have :code:`default` flag set. User can select desired parameter
variant with the command line::

  $ moulin xilinx-bsp.yaml --MACHINE qemu-zynq7

All entries from :code:`overrides` of the chosen parameter will be
applied on top of the build configuration. In this example, it will
overwrite :code:`MACHINE` variable with some meaningful value.


Parameterized build with multiple images
----------------------------------------

The following example is the most complex one. It shows the main reason why
`moulin` was written in the first place:

.. code-block:: yaml

		desc: "Renesas Gen3 build with Xen, Dom0 and DomD"
		variables:
		  MACHINE: "salvator-x-m3-xt"
		common_data:
		  sources: &COMMON_SOURCES
		    - type: git
		      url: "/home/lorc/mnt/ssd2/yovrin-test2/src/poky"
		      rev: 424296bf9bb4bae27febf91bce0118df09ce5fa1
		    - type: git
		      url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-virtualization"
		      rev: 92cd3467502bd27b98a76862ca6525ce425a8479
		    - type: git
		      url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-arm"
		      rev: f7c5e7d5094f65d105d9d580ba59527c25fb0d0f
		    - type: git
		      url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-openembedded"
		      rev: f2d02cb71eaff8eb285a1997b30be52486c160ae
		  conf: &COMMON_CONF
		    - [SSTATE_DIR, "${TOPDIR}/../common_data/sstate"]
		    - [DL_DIR, "${TOPDIR}/../common_data/downloads"]
		    # This is basically xt_shared_env.inc
		    # known domains
		    - [XT_DIR_REL_DOM0, "dom0"]
		    - [XT_DIR_REL_DOMD, "domd"]

		    # these are the folders within the domain's root filesystem where all
		    # installed artifacts live
		    - [XT_DIR_ABS_ROOTFS, "/xt"]

		    - [XT_DIR_ABS_ROOTFS_DOM0, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOM0}/"]
		    - [XT_DIR_ABS_ROOTFS_DOMD, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOMD}/"]
		    - [XT_DIR_ABS_ROOTFS_DOMA, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOMA}/"]
		    - [XT_DIR_ABS_ROOTFS_DOMF, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOMF}/"]
		    - [XT_DIR_ABS_ROOTFS_DOMR, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOMR}/"]
		    - [XT_DIR_ABS_ROOTFS_DOMU, "${XT_DIR_ABS_ROOTFS}/${XT_DIR_REL_DOMU}/"]

		    # these are folder names to be used across domains to install
		    # various types of artifacts
		    - [XT_DIR_ABS_ROOTFS_SCRIPTS, "${XT_DIR_ABS_ROOTFS}/scripts"]
		    - [XT_DIR_ABS_ROOTFS_CFG, "${XT_DIR_ABS_ROOTFS}/cfg"]
		    - [XT_DIR_ABS_ROOTFS_DOM_CFG, "${XT_DIR_ABS_ROOTFS}/dom.cfg"]

		components:
		  dom0:
		    # build-dir is optional
		    build-dir: shared-build2
		    sources:
		      - *COMMON_SOURCES

		    builder:
		      type: yocto
		      work_dir: build-dom0
		      conf:
		        - *COMMON_CONF
		        - [MACHINE, "generic-armv8-xt"]
		        - ["PREFERRED_PROVIDER_virtual/kernel", "linux-generic-armv8"]

		        # Remove ptest to reduce the build time
		        - [DISTRO_FEATURES_remove, "ptest"]

		        # For virtualization
		        - [DISTRO_FEATURES_append, " virtualization"]
		        - [DISTRO_FEATURES_append, " xen"]
		        # FIXME: normally bitbake fails with an error if there are bbappends w/o recipes

		        - [SERIAL_CONSOLES, ""]

		        # Disable shared link for GO packages
		        - [XT_GUESTS_INSTALL, "domu"]

		        - [MACHINEOVERRIDES_append, ":%{MACHINE}"]
		        - [TUNE_FEATURES_append, " cortexa57-cortexa53"]
		      external_src:
		        "domd-install-artifacts": "build-domd/tmp/deploy/images/%{MACHINE}/"

		      build_target: core-image-thin-initramfs
		      layers:
		        - "../poky/meta"
		        - "../poky/meta-poky"
		        - "../poky/meta-yocto-bsp"
		        - "../meta-arm/meta-arm-toolchain"
		        - "../meta-openembedded/meta-oe"
		        - "../meta-openembedded/meta-networking"
		        - "../meta-openembedded/meta-python"
		        - "../meta-openembedded/meta-filesystems"
		        - "../meta-virtualization"
		        # Use inner layers of meta-xt-images and meta-xt-prod-devel
		        - "../meta-xt-images/recipes-dom0/dom0-image-thin-initramfs/files/meta-xt-images-extra"
		        - "../meta-xt-images/recipes-domx/meta-xt-images-domx/"
		        - "../meta-xt-images/machine/meta-xt-images-generic-armv8"
		        - "../meta-xt-prod-devel/recipes-dom0/dom0-image-thin-initramfs/files/meta-xt-prod-extra"
		      target_images:
		        - "tmp/deploy/images/salvator-x/core-image-minimal-salvator-x.ext4"
		        - "tmp/deploy/images/salvator-x/bl2-salvator-x.bin"
		      # Dependencies from other layers (like domd kernel image, for example)
		      additional_deps:
		        - "build-domd/tmp/deploy/images/%{MACHINE}/Image"
		  domd:
		    # build-dir is optional
		    build-dir: shared-build2
		    sources:
		      - *COMMON_SOURCES
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-clang"
		        rev: e63d6f9abba5348e2183089d6ef5ea384d7ae8d8
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-python2"
		        rev: c96cfe30701ba191903c5f7d560c3ba667d46c9d
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-renesas"
		        rev: c0a59569d52e32c26de083597308e7bc189675dd
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-selinux"
		        rev: 7af62c91d7d00a260cf28e7908955539304d100d
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-xt-prod-devel"
		        rev: "REL-v6.0"
		      - type: git
		        url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-xt-images"
		        rev: "REL-v6.0"

		    builder:
		      type: yocto
		      work_dir: build-domd
		      conf:
		        - *COMMON_CONF
		        - [MACHINE, "%{MACHINE}"]
		        - [PREFERRED_VERSION_u-boot_rcar, "v2020.01%"]
		        # override console specified by default by the meta-rcar-gen3
		        # to be hypervisor's one
		        - [SERIAL_CONSOLES, "115200;hvc0"]

		        - [XT_GUESTS_INSTALL, "domu"]

		      build_target: core-image-weston
		      layers:
		        - "../poky/meta"
		        - "../poky/meta-poky"
		        - "../poky/meta-yocto-bsp"
		        - "../meta-renesas/meta-rcar-gen3"
		        - "../meta-arm/meta-arm-toolchain"
		        - "../meta-openembedded/meta-oe"
		        - "../meta-openembedded/meta-networking"
		        - "../meta-openembedded/meta-python"
		        - "../meta-openembedded/meta-filesystems"
		        - "../meta-selinux"
		        - "../meta-virtualization"
		        - "../meta-clang"
		        - "../meta-python2"
		        # Use inner layers of meta-xt-images and meta-xt-prod-devel
		        - "../meta-xt-images/recipes-domd/domd-image-weston/files_rcar/meta-xt-images-extra"
		        - "../meta-xt-images/recipes-domx/meta-xt-images-domx/"
		        - "../meta-xt-images/recipes-domx/meta-xt-images-vgpu/"
		        - "../meta-xt-images/machine/meta-xt-images-rcar-gen3"
		        - "../meta-xt-prod-devel/recipes-domd/domd-image-weston/files/meta-xt-prod-extra"
		      target_images:
		        - "tmp/deploy/images/%{MACHINE}/Image"

		parameters:
		  # Prebuilt DDK
		  USE_PREBUILT_DDK:
		    "no":
		      default: true
		      overrides:
		        components:
		          domd:
		            sources:
		              - type: git
		                url: "ssh://git@gitpct.epam.com/epmd-aepr/img-proprietary"
		                rev: "ef1aa566d74a11c4d2ae9592474030a706b4cf39"
		                dir: "proprietary"
		            builder:
		              conf:
		                - [PREFERRED_PROVIDER_gles-user-module, "gles-user-module"]
		                - [PREFERRED_VERSION_gles-user-module, "1.11"]

		                - [PREFERRED_PROVIDER_kernel-module-gles, "kernel-module-gles"]
		                - [PREFERRED_VERSION_kernel-module-gles, "1.11"]

		                - [PREFERRED_PROVIDER_gles-module-egl-headers, "gles-module-egl-headers"]
		                - [PREFERRED_VERSION_gles-module-egl-headers, "1.11"]
		                - [EXTRA_IMAGEDEPENDS_append, " prepare-graphic-package"]
		    "yes":
		      overrides:
		        components:
		          domd:
		            builder:
		              conf:
		                - [XT_RCAR_EVAPROPRIETARY_DIR, "./"]
		                - [PREFERRED_PROVIDER_virtual/libgles2, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_virtual/egl, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_kernel-module-pvrsrvkm, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_kernel-module-dc-linuxfb, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_kernel-module-gles, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_gles-user-module, "rcar-proprietary-graphic"]
		                - [PREFERRED_PROVIDER_gles-module-egl-headers, "rcar-proprietary-graphic"]
		                - [BBMASK_append, " meta-xt-images-vgpu/recipes-graphics/gles-module/"]
		                - [BBMASK_append, " meta-xt-prod-extra/recipes-graphics/gles-module/"]
		                - [BBMASK_append, " meta-xt-prod-vgpu/recipes-graphics/gles-module/"]
		                - [BBMASK_append, " meta-xt-prod-vgpu/recipes-graphics/wayland/"]
		                - [BBMASK_append, " meta-xt-prod-vgpu/recipes-kernel/kernel-module-gles/"]
		                - [BBMASK_append, " meta-xt-images-vgpu/recipes-kernel/kernel-module-gles/"]
		                - [BBMASK_append, " meta-renesas/meta-rcar-gen3/recipes-kernel/kernel-module-gles/"]
		                - [BBMASK_append, " meta-renesas/meta-rcar-gen3/recipes-graphics/gles-module/"]

		  # Machines
		  MACHINE:
		    salvator-x-m3-xt:
		      default: true
		      overrides:
		        variables:
		          MACHINE: "salvator-x-m3-xt"
		    salvator-x-h3-xt:
		      overrides:
		        variables:
		          MACHINE: "salvator-x-h3-xt"
		    h3ulcb-4x2g-kf-xt:
		      overrides:
		        variables:
		          MACHINE: "h3ulcb-4x2g-kf-xt"
		        components:
		          builder:
		            dom0:
		              conf:
		                - [MACHINEOVERRIDES_append, ":kingfisher"]
		            domd:
		              sources:
		                - type: git
		                  url: "/home/lorc/mnt/ssd2/yovrin-test2/src/meta-rcar"
		                  rev: a99eb54e9b068375b306fec53f1530f7eb780014
		              builder:
		                layers:
		                  - "../meta-rcar/meta-rcar-gen3-adas"
		                conf:
		                  #FIXME: patch ADAS: do not use network setup as we provide our own
		                  - [BBMASK "meta-rcar-gen3-adas/recipes-core/systemd"]
		                  # Remove development tools from the image
		                  - [IMAGE_INSTALL_remove " strace eglibc-utils ldd rsync gdbserver dropbear opkg git subversion nano cmake vim"]
		                  - [DISTRO_FEATURES_remove " opencv-sdk"]
		                  # Do not enable surroundview, which cannot be used
		                  - [DISTRO_FEATURES_remove " surroundview"]
		                  - [PACKAGECONFIG_remove_pn-libcxx "unwind"]


This is an example of a real build configuration file. It is still under
development, so unlike the two previous examples, you would not be able to
use this example to make a build. We would not cover it in detail,
just give you the list of highlights:

#. It builds two Yocto-based images: `dom0` and `domd`.
#. The same work directory is used, so builds can share repositories with layers.
#. There is :code:`common_data` section that provides some options
   that are shared by both builds: some source code and some
   `local.conf` entries.
#. :code:`external_src` option is used to provide build artifacts from
   one component into another. In this way, `Dom0` image can include
   Linux kernel image generated by `DomD`.
#. There are two parameters: :code:`MACHINE` and
   :code:`USE_PREBUILT_DDK`. This allows user to choose the target machine
   and build some proprietary drivers if they have access to
   the corresponding repository.
#. Local `git` repos are used.
