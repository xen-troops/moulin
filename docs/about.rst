About moulin
==========================

Main purpose of `moulin` is to build complex images for embedded
devices. Imagine that you are running hypervisor (like Xen or KVM) on
your device and you want to build multiple VM images with one simple
command. `moulin` is made exactly for this task.

But `moulin` also can be used to build simpler projects like
standalone Yocto distribution or AOSP. As `moulin` project file
includes both code location and build instructions, it is much easier
to invoke :code:`moulin myproject.yaml` to get the complete build than
to fumble with Yocto layers and configs.

Main purpose
------------

In modern world even embedded systems can benefit from virtualization
technologies. For example, ARMv8 architecture have built-in
virtualization extensions, so both Xen hypervisor and KVM can run on
variety of ARMv8-based SoCs. In embedded world it is natural to have
some way to build the whole bootable image with one command. But there
is no easy way to build multiple different virtual machine images. For
example, we want to build Linux-based host VM, Android and another
Linux distro as a guest VM. `moulin` was created exactly for this purpose.

Most of the modern BSPs are Yocto-based Linux distributions with
vendor-specific changes. Mobile chips likely will have Android Open
Source (AOSP) support as well. So right now `moulin` is focuses on
supporting this two build systems. More will be added later.

Design
------

`moulin` is not a replacement for `make` or `bitbake`. It merely
processes project YAML file and generates `Ninja
<https://ninja-build.org/>`_ build file. So, actual job runner is the Ninja.

On other hand, `moulin` project files describe the whole build, with
source code locations, build options, dependencies between images and
optional parameters.

Requirements and Installation
-----------------------------

`moulin` requires Python 3.6+ to run. You might need :code:`pip` or
:code:`pip3` tool to install it.

`moulin` generates `build.ninja` compatible with ninja 1.10+.
This is because lower versions of ninja do not support multiple outputs.
So if you run ninja and see error message like this ::

  multiple outputs aren't (yet?) supported by depslog

you need to get newer version from `<https://github.com/ninja-build/ninja/releases>`_.

Also `moulin` requires :code:`pygit2`. If it is not installed on your
system, :code:`pip` will try to install it from repository. It may
fail in case if you are missing :code:`libgit2` development files or
if installed :code:`libgit2` is too old. So, it is better to install
:code:`pygit2` globally. For example, on Ubuntu 18.04 you need to
install :code:`python3-pygit2` package.

`moulin` source code is stored at `GitHub
<https://github.com/xen-troops/moulin>`_.

Preferred way to install it right now is to put it your local per-user
storage using ::

  pip3 install --user git+https://github.com/xen-troops/moulin

command. Make sure that your :code:`PATH` environment variable
includes :code:`/home/${USER}/.local/bin`.

You can encounter problem with `pygit2` installation on some Ubuntu or
Debian distribution due to this
`bug <https://github.com/pypa/pip/issues/4222>`_. In this case you will
need to use the following command ::

  PIP_IGNORE_INSTALLED=0 pip3 install --user git+https://github.com/xen-troops/moulin

as a workaround.

Alternatively, you can clone the mentioned git repository and invoke
:code:`moulin.py` directly.
