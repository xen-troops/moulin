User reference manual
=====================

Invoking moulin
---------------

`moulin` has one mandatory parameter - file name of build
description. It should be in YAML format. List of supported keys is
provided in the next section.

As a result, `moulin` will generate :code:`ninja.build` file. You can
then invoke `ninja` to perform the actual build. `moulin` adds
`generator` rule in :code:`ninja.build`, so it is not mandatory to
invoke `moulin` after you made changes into your YAML file. `Ninja`
will detect any changes to this file and invoke `moulin` automatically
to re-create :code:`ninja.build`.

If YAML file contains :code:`parameters` key, it is possible to invoke
`moulin` with additional command line options. Set of this options
depends of contents of YAML file and can be viewed using
:code:`--help-config` command line option.

Verbose output
^^^^^^^^^^^^^^

Use :code:`-v` or :code:`--verbose` command line option to increase
verbosity of output. With this option enabled `moulin` will give more
information about what it is doing.

Dumping intermediate state
^^^^^^^^^^^^^^^^^^^^^^^^^^

:code:`--dump` command line option can be used to force `moulin` to
dump intermediate state of processed YAML file. You will see contents
of your build config after applying all parameters and expanding all
variables. This can come in help during debugging of your build,
because you can see what exactly is passed to fetchers and builders.

YAML sections
-------------

YAML file should consist of number of pre-defined keys/sections which are discussed below. Any
unknown keys are ignored. Right now only the following top-level keys are supported:

* :code:`desc` - mandatory
* :code:`min_ver` - optional
* :code:`components` - mandatory
* :code:`variables` - optional
* :code:`parameters` - optional

Minimal Version
^^^^^^^^^^^^^^^

Optional :code:`min_ver` section should hold minimal required version
of `moulin`. This is a text string that conforms `PEP-440
<https://www.python.org/dev/peps/pep-0440/>`_. For example
:code:`min_ver: "0.2"`. `moulin` will compare this with own version
and will stop if required version is newer.

Mandatory sections: "desc" and "components"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are only two mandatory sections: :code:`desc` and
:code:`components`. :code:`desc` should contain text string that
describes the build. It is displayed when `moulin` invoked with
:code:`--help-config` command line option.

:code:`components` should contain dictionary where key is a component
name and value is an another dictionary with component settings:

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

:code:`sources` should contain list of source code definition, which
will be fetched prior starting a build:

.. code-block:: yaml

    sources:
     - type: git
       url: "git://git.yoctoproject.org/poky"
       rev: gatesgarth
     - type: repo
       url: https://github.com/xen-troops/android_manifest.git
       rev: android-11-master
       manifest: doma.xml


All supported fetchers are listed in `Fetchers`_ section.

:code:`builder` contains build configuration for a given
component. There are multiple builder types supported. They are
described in `Builders`_ section.

Apart from two mandatory options, component description can contain following optional keys:

* :code:`build_dir` - build directory name. By default component's name is used.
* :code:`default` - if set to :code:`true` - tells Ninja that this
  component is a default build target. This can be omitted and Ninja
  will choose build target by own rules.

Variables
^^^^^^^^^

:code:`variables` section is optional. It can contain dictionary of variable's name-value pairs:

.. code-block:: yaml

  variables:
    A: "a"
    B: "1%{A}%{A}" # will be expanded to "1aa"
    C: "2%{B}%{B}" # will be expanded to "21aa1aa"


Variables can be used anywhere in the YAML file. During internal
pre-processing all variable references in form of
:code:`%{variable_name}` will be replaced with actual variable value.

:code:`%` is a special symbol. It can be escaped by doubling it: :code:`%%`.

Variables should be used to decrease amount of hard-coded values. Good
candidates  that should be moved to variables are path names,
branches, hardware identifiers, etc.

Parameters
^^^^^^^^^^

Often it is desired to have some options for a build. For example one
can want to support a number of different HW boards, or to enable
additional features. It would be not feasible to have separate YAML
for every board-feature combination. This is where parameters come to
help. All parameters should be stored in :code:`sources` section:

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
can have one or more options, one of option should have
:code:`default` flag enabled.

Main part of each option is the :code:`overrides` section. Contents of
this section should correspond to top-level layout of YAML file. All
contents of this section will be overlaid on contents of YAML file
during pre-processing stage. Rules of this process are:

* Dictionaries are extended with new keys from :code:`overrides` section.
* If dictionary already have the key:

  * If type of original value differs from type of :code:`overrides` section value, error is generated.
  * If key's value is a scalar (number, boolean, string) that it is replaced with value from :code:`overrides` section.
  * If key's value is an another dictionary, process start recursively.
  * If key's value is a list, it is expanded with values from :code:`overrides` section.

* Order of parameters application is not specified.

Basically, this rules follow the intuitive idea of
extending/overwriting original config: primitive values will be
overwritten, all other values will be extended.

User can chose parameter's options using command line arguments, as described in `Invoking moulin`_ section.

Fetchers
--------

Fetchers are the `moulin` plugins responsible for code download. Right
now only `git` and `repo` are supported. Fetchers are used to download
all sources listed in :code:`sources` section of a component.

`moulin` will generate phony Ninja target
:code:`fetch-{component_name}` for every component. It can be used to
just fetch sources without building anything.

git fetcher
^^^^^^^^^^^

`git` fetcher used to download code from a remote or local git
repositories. There is a full list of supported parameters:

.. code-block:: yaml

  type: git # Selects `git` fetcher
  url: "url://for.repository/project.git"
  rev: revision_name
  dir: "directory/where/store/code"



* :code:`type` - mandatory - should be :code:`git` to enable `git` fetcher.
* :code:`url` - mandatory - repository URL. You can provide any URL
  that is supported by `git` itself.
* :code:`rev` - optional - revision that should be checked out after
  cloning. Can be any `git` :code:`tree-ish` like branch name, tag or
  commit ID. If this option is omitted, `git` will checkout default branch.
* :code:`dir` - optional - directory name which should be used for
  cloning. If this option is missed, `moulin` will try to guess
  directory name from :code:`url`. This path is relative to
  component's build directory.

repo fetcher
^^^^^^^^^^^^

`repo` fetcher used to download code using Google's `repo` tool. Full
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
  :code:`--depth` option. Setting it to 1 will sufficiently decrease fetching time.
* :code:`groups` - optional - name of manifest groups that should be synced. Corresponds to `repo`'s
  :code:`-g` option. You can use it to chose which project groups needs to be synced.
* :code:`dir` - optional - directory name which should be used for
  code storage. If it is missing, `moulin` will use :code:`"."` to
  initialize `repo` repository right in component's build directory,
  as this is a main `repo` use case.

Builders
--------

Builders are the `moulin` plugins responsible for actual image building. Right
now only `yocto` and `android` are supported.

`moulin` will generate phony Ninja target
:code:`{component_name}` for every component. It can be used to
build certain component. Please note that this will not build **only**
given component. Any prerequisites will be fetched and build as well.

Builder configuration heavily depends on builder type and is described
in next subsections.

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
    layers:           # Mandatory
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
  same key.

* :code:`layers` - list of additional layers. Those layers will be
  added to the build using :code:`bitbake-layers add-layer {layers}`
  command.

* :code:`work_dir` - `bitbake`'s work directory. Default value is
  "build". This is where files like "conf/local.conf" are stored. You
  can overwrite so you can produce multiple builds from the same (or
  different) set of Yocto layers.

* :code:`additional_deps` - list of additional dependencies. This is
  basically :code:`target_images` produced by other components. You
  can use those to implement build dependencies between
  components. For example, if your system needs to have DomU's kernel
  image on Dom0 file system, you might want to add path to DomU's
  kernel into :code:`additional_deps` of Dom0's config. This will
  ensure that Dom0 will be built **after** DomU.

* :code:`external_src` - list of external sources for packages. This
  option will make `moulin` to generate
  :code:`EXTERNALSRC_pn-{package}` in `local.conf`. This feature is
  used to provide Yocto build with artifacts that were built outside
  of the tree. Such artifacts can be provided by another component,
  for example.

android builder
^^^^^^^^^^^^^^^

Android builder is used to build Android Open Source Project
(AOSP). It expects that AOSP is present in build directory. In most
cases AOSP is cloned using `repo` fetcher.

.. code-block:: yaml

  builder:
    type: android # Should be 'android'
    env:          # Optional
      - "TARGET_BOARD_PLATFORM=r8a7795"
    lunch_target: xenvm-userdebug
    target_images:
      - "out/xenvm/userdebug/boot.img"
      - "out/xenvm/userdebug/system.img"

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
