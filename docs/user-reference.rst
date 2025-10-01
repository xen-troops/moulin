Moulin User reference manual
============================

.. _invoking_moulin:

Invoking moulin
---------------

`moulin` has one mandatory parameter - the file name of the build
description. It should be in YAML format.
You may use a regular local file or URL. `moulin` detects
URL by the presence of a protocol prefix, like `https://`.
If you use the URL to GitHub or another network repository,
you can use the URL for the raw file only, not for a web
page with that file.
For example, this URL points to the correct YAML file:
`https://raw.githubusercontent.com/xen-troops/meta-xt-prod-devel-rcar/master/prod-devel-rcar.yaml`.
But the following URL can't be used, because it points to
GitHub's web page:
`https://github.com/xen-troops/meta-xt-prod-devel-rcar/blob/master/prod-devel-rcar.yaml`.
Pay attention, that file will be downloaded only if a file
with the same name doesn't exist in the current folder.
This is done to preserve possible local changes made by a user.

As a result, `moulin` will generate :code:`ninja.build` file. You can
then invoke `ninja` to perform the actual build. `moulin` adds
`generator` rule in :code:`ninja.build`, so it is not mandatory to
invoke `moulin` after you make changes to your YAML file. `Ninja`
will detect any changes to this file and invoke `moulin` automatically
to re-create :code:`ninja.build`.

If the YAML file contains :code:`parameters` key, it is possible to invoke
`moulin` with additional command line options. The set of these options
depends on the contents of the YAML file and can be viewed using
:code:`--help-config` command line option.

Verbose output
^^^^^^^^^^^^^^

Use :code:`-v` or :code:`--verbose` command line option to increase
the verbosity of the output. With this option enabled, `moulin` will give more
information about what it is doing.

Dumping intermediate state
^^^^^^^^^^^^^^^^^^^^^^^^^^

:code:`--dump` command line option can be used to force `moulin` to
dump the intermediate state of the processed YAML file. You will see the contents
of your build config after applying all parameters and expanding all
variables. This can come in handy during the debugging of your build,
because you can see what exactly is passed to fetchers and builders.

.. _moulin_yaml_sections:

Internal command line options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There is :code:`--fetcherdep` command line option which is internal,
and it is even hidden from :code:`-h` output. It is used by `moulin` to
generate dynamic dependency files for Ninja, so Ninja can track changes
inside components.

This option is not meant to be used by a user.

YAML sections
-------------

The YAML file should consist of several predefined keys or sections, which are discussed below. Any
unknown keys are ignored. Right now, only the following top-level keys are supported:

* :code:`desc` - mandatory
* :code:`min_ver` - optional
* :code:`components` - mandatory
* :code:`images` - optional. See `rouge` documentation.
* :code:`variables` - optional
* :code:`parameters` - optional

Minimal Version
^^^^^^^^^^^^^^^

Optional :code:`min_ver` section should hold the minimal required version
of `moulin`. This is a text string that conforms to `PEP-440
<https://www.python.org/dev/peps/pep-0440/>`_. For example
:code:`min_ver: "0.2"`. `moulin` will compare this with its own version
and will stop if the required version is newer.

Mandatory sections: "desc" and "components"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are only two mandatory sections: :code:`desc` and
:code:`components`. :code:`desc` should contain a text string that
describes the build. It is displayed when `moulin` is invoked with
:code:`--help-config` command line option.

:code:`components` should contain a dictionary where the key is a component
name and value is another dictionary with component settings:

.. code-block:: yaml

   components:
       component1:
           build-dir: "component-build-dir" # Optional
	   default: true # Optional
           sources:
	       ......
	   builder:
	       .....
       component2:
           sources:
	       ......
	   builder:
	       .....

There are two main parts of each `component` description: :code:`sources` and :code:`builder`.

:code:`sources` is optional and can contain a list of source code definitions, which
will be fetched before starting a build:

.. code-block:: yaml

    sources:
     - type: git
       url: "git://git.yoctoproject.org/poky"
       rev: gatesgarth
     - type: repo
       url: https://github.com/xen-troops/android_manifest.git
       rev: android-11-master
       manifest: doma.xml


All supported fetchers are listed in the `Fetchers`_ section.

:code:`builder` contains build configuration for a given
component. There are multiple builder types supported. They are
described in the `Builders`_ section.

Apart from two mandatory options, component description can contain the following optional keys:

* :code:`build_dir` - build directory name. By default, the component's name is used.
* :code:`default` - if set to :code:`true` - tells Ninja that this
  component is a default build target. This can be omitted and Ninja
  will choose the build target on its own rules.

Variables
^^^^^^^^^

:code:`variables` section is optional. It can contain a dictionary of variable name-value pairs:

.. code-block:: yaml

  variables:
    A: "a"
    B: "1%{A}%{A}" # will be expanded to "1aa"
    C: "2%{B}%{B}" # will be expanded to "21aa1aa"


Variables can be used anywhere in the YAML file. During internal
pre-processing all variable references in the form of
:code:`%{variable_name}` will be replaced with the actual variable value.

:code:`%` is a special symbol. It can be escaped by doubling it: :code:`%%`.

Variables should be used to decrease the amount of hard-coded values. Good
candidates  that should be moved to variables are path names,
branches, hardware identifiers, etc.

Parameters
^^^^^^^^^^

Often, it is desired to have some options for a build. For example, one
can want to support several different HW boards or to enable
additional features. It would not be feasible to have separate YAML
for every board-feature combination. This is where parameters come to
help. All parameters should be stored in :code:`parameters` section:

.. code-block:: yaml

  parameters:
    parameter1:
      desc: "parameter 1 description"
      option1:
        default: true
	overrides:
	  ...
      option2:
	overrides:
	  ...
      option3:
	overrides:
	  ...
    parameter2:
      desc: "parameter 2 description"
      option1:
	overrides:
	  ...
      option2:
	overrides:
	  ...
      option3:
        default: true
	overrides:
	  ...


Every parameter should include mandatory :code:`desc` key. Parameter
can have one or more options, one of which should have
:code:`default` flag enabled.

Central part of each option is the :code:`overrides` section. Contents of
this section should correspond to the top-level layout of the YAML file. All
contents of this section will be overlaid on the contents of the YAML file
during the pre-processing stage. Rules of this process are:

* Dictionaries are extended with new keys from :code:`overrides` section.
* If the dictionary already has the key:

  * If type of original value differs from type of :code:`overrides` section value, error is generated.
  * If key's value is a scalar (number, boolean, string) that it is replaced with value from :code:`overrides` section.
  * If key's value is an another dictionary, process start recursively.
  * If key's value is a list, it is expanded with values from :code:`overrides` section.

* Order of parameter application is not specified.

Basically, these rules follow the intuitive idea of
extending/overwriting original config: primitive values will be
overwritten, all other values will be extended.

User can choose parameter options using command line arguments, as described in the `Invoking moulin`_ section.

Fetchers
--------

Fetchers are the `moulin` plugins responsible for downloading
sources listed in :code:`sources` section of a component.

`moulin` will generate phony Ninja target
:code:`fetch-{component_name}` for every component. It can be used to
just fetch sources without building anything.

git fetcher
^^^^^^^^^^^

`git` fetcher is used to download code from a remote or local git
repository. There is a complete list of supported parameters:

.. code-block:: yaml

  type: git # Selects `git` fetcher
  url: "url://for.repository/project.git"
  rev: revision_name
  dir: "directory/where/store/code"
  depth: 1
  submodules: true



* :code:`type` - mandatory - should be :code:`git` to enable `git` fetcher.
* :code:`url` - mandatory - repository URL. You can provide any URL
  that is supported by `git` itself.
* :code:`rev` - optional - revision that should be checked out after
  cloning. Can be any `git` :code:`tree-ish` like branch name, tag, or
  commit ID. If this option is omitted, `git` will checkout the default branch.
* :code:`dir` - optional - directory name which should be used for
  cloning. If this option is missed, `moulin` will try to guess
  the directory name from :code:`url`. This path is relative to
  the component's build directory.
* :code:`submodules` - optional - boolean. Fetch submodules along with
  main repository.
* :code:`depth` - optional - cloning depth. Corresponds to :code:`--depth`
  option for :code:`git clone`. If used together with :code:`submodules`
  enabled, it will call :code:`git`  with :code:`--shallow-submodules`

repo fetcher
^^^^^^^^^^^^

`repo` fetcher is used to download code using Google's `repo` tool. Full
list of supported options:

.. code-block:: yaml

  type: repo # Selects `repo` fetcher
  url: https://manifest.address/repo.git
  rev: manifest-revision
  manifest: manifest-file.xml
  depth: 1
  groups: all
  dir: "."

* :code:`type` - mandatory - should be :code:`repo` to enable `repo` fetcher.
* :code:`url` - mandatory - manifest repository URL. You can provide
  any URL that is supported by `repo` itself. This corresponds to
  `repo`'s :code:`-u` option.
* :code:`rev` - optional - manifest revision. Corresponds to `repo`'s
  :code:`-b` option.
* :code:`manifest` - optional - manifest file name. Corresponds to `repo`'s
  :code:`-m` option.
* :code:`depth` - optional - cloning depth of internal repositories. Corresponds to `repo`'s
  :code:`--depth` option. Setting it to 1 will sufficiently decrease the fetching time.
* :code:`groups` - optional - name of manifest groups that should be synced. Corresponds to `repo`'s
  :code:`-g` option. You can use it to choose which project groups need to be synced.
* :code:`dir` - optional - directory name which should be used for
  code storage. If it is missing, `moulin` will use :code:`"."` to
  initialize `repo` repository right in the component's build directory,
  as this is a main `repo` use case.


http fetcher
^^^^^^^^^^^^^^

`http` fetcher is used to download a file via HTTP or HTTPS protocol. It uses
:code:`curl` tool to do so. Complete list of supported options:

.. code-block:: yaml

  type: http # Selects `http` fetcher
  url: "https://example.com/file.txt"
  filename: "file.txt"
  dir: "."

* :code:`type` - mandatory - should be :code:`http` to use `http`
  fetcher. Use the same type even if you are downloading over the HTTPS
  protocol.
* :code:`url` - mandatory - URL of a file to be downloaded
* :code:`filename` - optional (in most cases) - name of the output
  file. If omitted, `moulin` will try to guess it from a URL. But if
  you can't do so, it will ask you to provide the filename manually.
* :code:`dir` - optional - directory name where to store a downloaded
  file. If it is omitted, `moulin` will use :code:`"."` to download a
  file right into the component's root directory.

unpack fetcher
^^^^^^^^^^^^^^

`unpack` fetcher is used to unpack already available archives to a
specified directory. An example use case is when we need to use a 3rd-party
code/resources that are not available in the git repository. Complete list of
supported options:

.. code-block:: yaml

  type: unpack # Selects `unpack` fetcher
  archive_type: tar
  file: my_file.tar.gz
  dir: "."

* :code:`type` - mandatory - should be :code:`unpack` to enable `unpack` fetcher.
* :code:`archive_type` - mandatory - type or archive. Now :code:`tar` and :code:`zip` are supported.
* :code:`file` - mandatory - name of the archive file
* :code:`dir` - optional - directory name which should be used for
  code storage. If it is missing, `moulin` will use :code:`"."` to
  unpack the archive right into the component directory.

Currently, :code:`unpack` fetcher supports two archive types: :code:`tar` and :code:`zip`.

* :code:`tar` actually supports not only plain `.tar` archives, but
  also compressed archives like `.tar.gz`, `.tar.bz2`, and so on. We
  rely on `tar` ability to select the right decompressor automatically.
* :code:`zip` - this is classic `zip` format. :code:`unzip` tool is
  used to decompress this kind of archive, so it should be present on
  the user's machine.

west fetcher
^^^^^^^^^^^^

`west` fetcher is used to download code using Zephyr's `west` meta-tool.
Complete list of supported options:

.. code-block:: yaml

  type: west # Selects `west` fetcher
  url: https://manifest.address/zephyr
  rev: manifest-revision
  file: manifest-file.yml

* :code:`type` - mandatory - should be :code:`west` to enable `west` fetcher.
* :code:`url` - optional - manifest repository URL. You can provide
  any URL that is supported by `west` itself. This corresponds to
  `west init`'s :code:`-m` option.
* :code:`rev` - optional - manifest revision. Corresponds to `west init`'s
  :code:`--mr` option.
* :code:`file` - optional - manifest file name. Corresponds to `west init`'s
  :code:`--mf` option.

For additional details, see documentation on `west init`:
https://docs.zephyrproject.org/latest/develop/west/built-in.html#west-init

Regarding installation of `west`, please see:
https://docs.zephyrproject.org/latest/develop/west/install.html

null fetcher
^^^^^^^^^^^^

`null` fetcher does nothing. It can be used for testing or in some
tricky situation when you want to have a component without fetchers.

.. code-block:: yaml

  type: "null" # Selects `none` fetcher

* :code:`type` - mandatory - should be :code:`"null"` to use `null` fetcher.
  Please note that you need to use quotes; otherwise, the YAML parser will
  treat it as a `null` type.

Builders
--------

Builders are the `moulin` plugins responsible for actual image building.

`moulin` will generate phony Ninja target
:code:`{component_name}` for every component. It can be used to
build a certain component. Please note that this will not build **only**
given component. Any prerequisites will be fetched and built as well.

Builder configuration heavily depends on the builder type and is described
in the next subsections.

yocto builder
^^^^^^^^^^^^^

Yocto builder is used to build OpenEmbedded-based images. It expects
that `poky` repository is cloned in :code:`{build_dir}/poky` and uses
it's :code:`poky/oe-init-build-env` script to initialize build
environment. Then :code:`bitbake-layers` tool is used to add
additional layers and :code:`bitbake` used to perform the build.

.. code-block:: yaml

  builder:
    type: yocto       # Should be `yocto`
    work_dir: "build" # Optional
    build_target: core-image-minimal # Mandatory
    conf:             # Mandatory
      - [MACHINE, "machine-name"]
      - [DISTRO_FEATURES_remove, "feature_to_remove"]
      - [DISTRO_FEATURES_append, "feature_to_add"]
    layers:           # Optional
      - "../poky/meta-yocto-bsp"
      - "../meta-other-layer/"
    external_src:     # Optional
      "package-name": "path-to-package-sources"
      "another-package-name": ["path part1", "path part2", "path part3"]
    target_images:    # Mandatory
      - "tmp/deploy/images/machine-name/Image"
    additional_deps:  # Optional
      - "path/to/file/generated/by/other/component"

Mandatory options:

* :code:`type` - Builder type. Should be :code:`yocto` for this type
  of builder.

* :code:`build_target` - `bitbake`'s build target. This will be used
  to run the build: :code:`$ bitbake {build_target}`

* :code:`target_images` - list of image files that should be generated
  by this component as a result of invoking :code:`$ bitbake
  {build_target}`. Every component should generate at least one image
  file.

Optional parameters. Those provide advanced features that may be
needed if you are building multiple VMs with cross-dependencies.

* :code:`conf` - list of additional :code:`local.conf` options. Please
  note that each entry in :code:`conf` list is not a :code:`key:value`
  pair, but another list of two items. We use this format because it
  is possible to have multiple :code:`local.conf` entries with the
  same key. Those entries will not be written straight into
  :code:`local.conf`. Instead, a new file :code:`moulin.conf` will be
  created. This file will then be included from :code:`local.conf`.

* :code:`layers` - list of additional layers. Those layers will be
  added to the build using :code:`bitbake-layers add-layer {layers}`
  command.

* :code:`work_dir` - `bitbake`'s work directory. The default value is
  "build". This is where files like "conf/local.conf" are stored. You
  can overwrite so you can produce multiple builds from the same (or
  different) set of Yocto layers.

* :code:`additional_deps` - list of additional dependencies. This is
  basically :code:`target_images` produced by other components. You
  can use those to implement build dependencies between
  components. For example, if your system needs to have DomU's kernel
  image on Dom0's file system, you might want to add the path to DomU's
  kernel into :code:`additional_deps` of Dom0's config. This will
  ensure that Dom0 will be built **after** DomU.

* :code:`external_src` - list of external sources for packages. This
  option will make `moulin` generate
  :code:`EXTERNALSRC:pn-{package}` in `local.conf`. This feature is
  used to provide the Yocto build with artifacts that were built outside
  of the tree. Such artifacts can be provided by another component,
  for example.

bazel builder
^^^^^^^^^^^^^

Bazel builder is used to build projects based on the Bazel build system
provided by Google. It expects that a project with source and Bazel
configuration files is present in the build directory.

.. code-block:: yaml

  builder:
    type: "bazel"         # Mandatory and must be `bazel`
    tool: "tools/bazel"   # Optional
    startup-options:      # Optional
      - "--max_idle_secs=1"
    command: run          # Optional
    args:                 # Optional
      - "--verbose_failures"
      - "--sandbox_debug"
    target:               # Mandatory
    target-patterns:      # Optional
      - "--dist_dir=path_to_dist"
    target_images:        # Mandatory
      - "out/deploy/virtual-device/virtual_device_aarch64/Image"
      - "out/deploy/virtual-device/virtual_device_aarch64/initramfs.img"

Mandatory parameters:

* :code:`type` - Builder type. It must be :code:`bazel` for this type
  of builder.

* :code:`target` - target name that should be described in the
  corresponding BUILD.bazel file and must satisfy bazel rules.

* :code:`target_images` - list of artifact files that should be generated
  by this component as a result of the build.
  Every component should generate at least one image file.

Optional parameters:

* :code:`tool` - the relative path to the Bazel tool in relation to the
  'build-dir'. If this parameter is not defined, the system-installed
  Bazel tool will be used.

* :code:`startup-options` - Bazel startup options that appear before
  the command and are parsed by the client.

* :code:`command` - bazel command. By default, :code:`build` is used.

* :code:`args` - bazel arguments related to the concrete :code:`command`.

* :code:`target-patterns` - bazel target patterns to be built or
  parameters to the executable target.

android builder
^^^^^^^^^^^^^^^

Android builder is used to build the Android Open Source Project
(AOSP). It expects that AOSP is present in the build directory. In most
cases, AOSP is cloned using the `repo` fetcher.

.. code-block:: yaml

  builder:
    type: android # Should be 'android'
    env:          # Optional
      - "TARGET_BOARD_PLATFORM=r8a7795"
    lunch_target: xenvm-userdebug
    target_images:
      - "out/xenvm/userdebug/boot.img"
      - "out/xenvm/userdebug/system.img"
    additional_deps:  # Optional
      - "path/to/file/generated/by/other/component"

Mandatory options:

* :code:`type` - Builder type. Should be :code:`android` for this type
  of builder.

* :code:`lunch_target` - `lunch`'s build target. This will be used
  to run the build: :code:`$ lunch {lunch-target}`

* :code:`target_images` - list of image files that should be generated
  by this component as a result of invoking :code:`$ m`. Every
  component should generate at least one image file.

Optional parameters:

* :code:`env` - list of additional environment variables that should
  be exported before calling :code:`lunch`.

android_kernel builder
^^^^^^^^^^^^^^^^^^^^^^

Android Kernel builder is used to build the kernel and kernel modules for
Android Open Source Project (AOSP). It expects that the correct directory
layout is present in the build directory. In most cases, AOSP is cloned
using the `repo` fetcher.

.. code-block:: yaml

  builder:
    type: android_kernel # Should be 'android_kernel'
    env:                 # Optional
      - "TARGET_BOARD_PLATFORM=r8a7795"
      - "BUILD_CONFIG=common/build.config.xenvm"
      - "SKIP_MRPROPER=1"
    target_images:
      - "out/android12-5.4/common/arch/arm64/boot/Image"

Mandatory options:

* :code:`type` - Builder type. Should be :code:`android_kernel` for
  this type of builder.

* :code:`target_images` - list of image files that this component
  should generate as a result of invoking :code:`build.sh`
  script. Every component should generate at least one image file.

Optional parameters:

* :code:`env` - list of additional environment variables that should
  be exported before calling :code:`build.sh`.

* :code:`additional_deps` - list of additional dependencies. This is
  basically :code:`target_images` produced by other components. You
  can use those to implement build dependencies between
  components. For example, if your Android build needs a Linux kernel
  built by some other component, you might want to add path to linux
  kernel image provided by this component into
  :code:`additional_deps`. This will ensure that Linux kernel will be
  built **before** Android.

archive builder
^^^^^^^^^^^^^^^

Archive builder is intended to create an archive from other components.
It can be used to gather build artifacts, for example. This builder
uses `tar` to create archive files. Archives can be optionally compressed
as, `tar` is invoked with `--auto-compress` option.

.. code-block:: yaml

  builder:
    type: archive        # Should be 'archive'
    name: "artifacts.tar.bz2"
    base_dir: "yocto/build/tmp/deploy/images/"
    items:
      # items are relative to base_dir
      - "generic-armv8-xt/Image"
      - "generic-armv8-xt/uInitramfs"

Mandatory options:

* :code:`type` - Builder type. It should be :code:`archive` for this type
  of builder.

* :code:`name` - Name of an archive file. Add a suffix like `tar.bz2` to
  make `tar` compress archive with desired compressing algorithm.

* :code:`base_dir` - Optional parameter specifying `tar`'s base directory.
  The default value is "." if not specified. This is passed to `tar` as
  `-C` option. As result, the final archive will contain paths relative
  to :code:`base_dir`. Avoid using `..` because specified items will be
  archived by `tar` but all `..` will be stripped. As a result, the archive
  will contain items with unexpected paths.

* :code:`items` - list of files or directories that should be added
  to the archive. Please ensure that those files or directories are present
  in other components :code:`target_images` sections, so Ninja can
  build correct dependencies. All paths are relative to the :code:`base_dir`.

zephyr builder
^^^^^^^^^^^^^^

This builder is used to build applications based on Zephyr OS.
It uses Zephyr OS meta-tool `west`. Required code is expected
to be fetched by `west` fetcher.

.. code-block:: yaml

  builder:
    type: zephyr
    board: xenvm
    shields:          # Optional
      - "shield1"
      - "shield2"
    target: samples/synchronization
    work_dir: build_dir
    target_images:
      - "zephyr/build/zephyr/zephyr.bin"
    vars:
      - "VAR1=var1_value"
    env:
      - "MY_ENV_VAR=my_value"
    additional_deps:  # Optional
      - "path/to/file/generated/by/other/component"


Mandatory options:

* :code:`type` - builder type. Should be :code:`zephyr` for this type
  of builder.

* :code:`board` - target board name. For example: `xenvm` or `xenvm_gicv3`
  for Xen-based builds. Corresponds to `west build`'s :code:`-b` option.
  See Zephyr's documentation for the list of allowed values.

* :code:`target` - build target. This will be used to run the build:
  :code:`$ west build {target}`. For example: `samples/synchronization` or
  `samples/hello_world`.

* :code:`target_images` - list of image files that this builder should generate.
  For the standard build, it is expected to be "zephyr/build/zephyr/zephyr.bin"

Optional parameters:

* :code:`env` - list of additional environment variables that should
  be exported before calling :code:`west build`.

* :code:`work_dir` - build system's work directory. Default value is
  "build". This is where files produced by the build system are stored.

* :code:`additional_deps` - list of additional dependencies. This is
  basically :code:`target_images` produced by other components. You
  can use those to implement build dependencies between
  components. For example, if your system needs to have DomU's kernel
  image in your zephyr image, you might want to add the path to DomU's
  kernel into :code:`additional_deps` of zephyr's config. This will
  ensure that zephyr will be built **after** DomU.

* :code:`shields` - list of shields should be integrated to zephyr board(For Zephyr < 3.4.0).

* :code:`snippets` - list of snippets should be integrated to zephyr board(For Zephyr >= 3.4.0).
  Please note that only one of :code:`shields` and :code:`snippets` can be used at the same time.

* :code:`vars` - list of additional variables that should be passed to CMake
  via :code:`west build`.

Please note that this builder uses :code:`--pristine=auto` command-line option.

Proper versions of CMake and the Zephyr SDK must be installed on the host.

For additional details, please see
https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#building-west-build

custom_script builder
^^^^^^^^^^^^^^^^^^^^^

The custom-script builder is designed to perform custom actions. This builder
actually calls the script pointed in option :code:`script`. Builder node
is stored in the file in :code:`work_dir` directory, and that file is passed to the
script as parameter

.. code-block:: yaml

  builder:
    type: custom_script        # Should be 'custom_script'
    work_dir : "script_workdir"
    script: "path/to/script/custom_script.py"
    args:
      - "argument1"
      - "argument2"
    config:
      items:
        "rootfs": "images/spider/rootfs.tar.bz2"
      manifest:
        "id": ""
        "vendorVersion": "0.2.0"
        "fileName": "archive.squashfs"
        "description": "DomD image"
        "bundleType": "full"
    target_images:
      - "custom_script_targets"
    additional_deps:  # Optional
      - "path/to/file_name"

Mandatory options:

* :code:`type` - Builder type. It should be :code:`custom_script` for this type
  of builder.

* :code:`work_dir` - build script work directory. Default value is "script_workdir".
  This is where files produced by the build system are stored.

* :code:`script` - path to script which performs custom actions. Whole yaml node will
  be stored to a file, and the name of that file will be passed to :code:`script` as
  the last command line argument.

* :code:`target_images` - list of files that should be generated by script.

Optional parameters:

* :code:`args` - additional arguments should be passed to :code:`script`. Can be passed as
  a string or a list

* :code:`additional_deps` - list of additional dependencies. This is
  basically :code:`target_images` produced by other components. You
  can use those to implement build dependencies between
  components. For example, if your system needs to have DomU's kernel
  image for your fota archive, you might want to add the path to DomU's
  kernel into :code:`additional_deps` of Dom0's config. This will
  ensure that the FOTA archive will be built **after** DomU.

* Remaining parameters should be parsed and used by the script pointed in
  :code:`script` option.


null builder
^^^^^^^^^^^^

"null" builder does nothing at all. It does not even generate
dependencies. It can be used for testing or in cases when you need to
call the fetcher only. Please note that Ninja will not call fetcher for
the component if fetcher's output file is not used by anything.

.. code-block:: yaml

  builder:
    type: "null"        # Should be "null"

Mandatory options:

* :code:`type` - Builder type. It should be :code:`"null"` for this type
  of builder. Please note that you need to use quotes; otherwise, the YAML parser will
  treat it as a `null` type.
