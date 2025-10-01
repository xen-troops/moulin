Usage notes
===========

Component-specific targets
--------------------------

As mentioned in chapters "Fetchers" and "Builders" of "User reference
manual", :code:`moulin` generates some helpful targets for components:
to fetch sources, to create a configuration, to build the component.
For example, if we have a component :code:`domu`, we will have the following
self-explanatory targets:

* :code:`fetch-domu`
* :code:`conf-domu`
* :code:`domu`

Rouge-specific targets
----------------------

If section :code:`images:` is present in YAML file, :code:`moulin`
will also generate handy :code:`image-{image_name}` rules. They can be
used to invoke :code:`rouge` with the same build options, as
:code:`moulin` was invoked.

Moulin also generates :code:`{image_name}.img.gz` and :code:`{image_name}.img.bmap`
targets.

Build inside yocto
------------------

If your component has yocto builder and you need to work inside the
components' build environment, then you need to specify the corresponding
build folder (see :code:`work_dir` parameter in :code:`builder` section
of required component) as a parameter to :code:`oe-init-build-env`.
For example to build only :code:`kernel-module-gles` in :code:`domd`:

.. code-block:: bash

  $ cd yocto
  $ . poky/oe-init-build-env build-domd
  $ bitbake kernel-module-gles

