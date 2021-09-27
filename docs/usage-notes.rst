Usage notes
===========

Component-specific targets
--------------------------

As mentioned in chapters "Fetchers" and "Builders" of "User reference
manual", :code:`moulin` generates some helpful targets for components:
to fetch sources, to create a configuration, to build the component.
For example, if we have component :code:`domu`, we will have following
self-explanatory targets:

* :code:`fetch-domu`
* :code:`conf-domu`
* :code:`domu`

Build inside yocto
------------------

If your component has yocto builder and you need to work inside the
components's build environment then you need to specify corresponding
build folder (see :code:`work_dir` parameter in :code:`builder` section
of required component) as a parameter to :code:`oe-init-build-env`.
For example to build only :code:`kernel-module-gles` in :code:`domd`:

.. code-block:: bash

  $ cd yocto
  $ . poky/oe-init-build-env build-domd
  $ bitbake kernel-module-gles

