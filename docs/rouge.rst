Rouge User Reference Manual
============================

About
-----

`rouge` is a companion tool for `moulin`. Its purpose is to simplify
the creation of bootable images. It can create a partition table, fill
partitions with predefined files or raw data. It supports GPT, ext4fs,
raw images, and Android sparse images. Further formats can be added if
needed.

Right now, it can be used only as a separate tool, but there are plans
to integrate it into `moulin` output.

Design Principles
-----------------

`rouge` shares ideas (and code) with `moulin`. Thus, it is very
similar in configuring and invoking to `moulin`. It can be used as a
stand-alone tool: provide only :code:`images:` section in your
YAML file. Or you can include this section in the same file, which
is used by `moulin` to share common options or variables. In the latter
case, `moulin` will generate additional :code:`image-{image_name}`
rules so that you can build images with Ninja.

Requirements
------------

To perform its function, `rouge` invokes several external utilities. Most of
them are available on every system, with the following exceptions:

 - To work with `vfat`, install the `mtools` package.
 - To work with Android, install the `simg2img` package.

There is a list of external tools used for the generation of images:

 - `dd` - used to copy raw images
 - `mkfs.ext4` - creates ext4 FS
 - `mkfs.vfat` - creates vfat FS
 - `simg2img` - used to unpack Android sparse image files
 - `mcopy` and `mdd` - to handle vfat images


Invoking `rouge`
----------------

`rouge` uses the same design ideas as `moulin`, and part of the
command line options are shared with `moulin`. This includes
:code:`--help-config`, :code:`-v`, and :code:`--dump` arguments. Please
refer to :ref:`moulin <invoking_moulin>` documentation for more
details. This document describes only arguments specific to `rouge`.

.. code-block::

   rouge [-h] [--help-config] [-v] [--dump] [-l] [-f] [-s] [-o FILE]
		[-l | -i image_name]
                build.yaml image_name

..

 - :code:`-i image_name` - name of one of the images described in
   :code:`images:` section of your build configuration file
   (:code:`build.yaml`). Basically, this is the image you want to create.

 - :code:`-l`, :code:`--list-images` - list available images and their
   descriptions. Please note that the actual list of images can depend on
   build config parameter values. For example, your build config may
   provide an option to enable Android build. If this option is enabled,
   you may have a separate image for Android.

 - :code:`-f`, :code:`--force` - force overwrite existing file. If
   this option is not given, `rouge` will refuse to create an image if
   the output file already exists.

 - :code:`-s`, :code:`--special` - allow to write to a special file,
   like a block device. Without this option, `rouge` will refuse to
   write to, say, :code:`/dev/sda`. Use this option with care and
   always double-check the device name, as `rouge` will overwrite anything
   that is stored on that device.

 - :code:`-o` - provides output file name. This is an optional parameter,
   by default, `rouge` will write to :code:`<image_name>.img`.


Apart from these options, `rouge` will read and parse all YAML file-related
parameters in the same way as `moulin` does. You can check
available parameters with :code:`--help-config`.

Principles of Operation
-----------------------

`rouge` works in a very simple way. It uses `moulin`'s YAML processor
that applies parameters and substitutes variables, then reads
:code:`images:` section, finds the requested image specification.

For a given image, it checks if all mentioned files are present, then
calculates the sizes of partitions (if any) and the total image size. Then it
writes data to a given file/block device according to the
specifications.

`rouge` tries to use sparse files whenever possible. A sparse file is a
file with "holes" in it. It allows you to have a huge file that
represents a whole disk image with a tiny bit of actual information in
it. This speeds up the image creation process and decreases the used disk
space. If you are writing the resulting image file to your SD card
manually, try adding :code:`conv=sparse` option to your :code:`dd`
command line. This will speed up the writing process. If you want to
distribute resulting images, take a look at Intel's :code:`bmap`
tool. It allows you to share sparse files across devices.

YAML Sections
-------------

Shared sections
^^^^^^^^^^^^^^^

`rouge` uses the same YAML processing code as `moulin` so refer to
`moulin`'s :ref:`documentation <moulin_yaml_sections>` for the
:code:`desc`, :code:`min_ver`, :code:`variables`, :code:`parameters`
sections description. This page describes only parts specific to `rouge`.

Image specifications
^^^^^^^^^^^^^^^^^^^^

Images are specified in the following way:

.. code-block:: yaml

   images:
     image_name_a:
       desc: "Description for the first image"
       image_size: 512 MiB
       type: gpt
       ... block description ...
     image_name_b:
       desc: "Description for the second image"
       type: raw_image
       ... block description ...
     image_name_c:
       desc: "Description for the third image"
       type: empty
       ... block description ...


:code:`images:` section contains one or more keys, which serve as
image names. Every image can have a description, which will be displayed
when `rouge` lists available images. :code:`type:` key is mandatory as
it defines the type of block. Supported block types are described in the
following sections.

Also, you may specify the required size of the image using
:code:`image_size:`. Please see the section 'Size Designation' below for
supported notation. If the actual size of all partitions will be less than
:code:`image_size:` then image will be blown up to :code:`image_size:`.
If the actual size is bigger than specified, an error will be printed with
an explanation like "Actual size (20000) of image is bigger than requested
one (10000)."

Block descriptions
------------------

"Block" is a basic `rouge` entity that describes one partition or
partition table. Some block types can be nested. Supported block types
are described below.

Size Designation
^^^^^^^^^^^^^^^^

All blocks have :code:`size` parameter. For some block types, this
parameter is mandatory, for some - optional. The basic unit for size is a byte.
For example

.. code-block:: yaml

   type: empty
   size: 4096

defines an empty block with a size of 4096 bytes. `rouge` supports some SI suffixes:

 - :code:`KB` - kilobyte - 1000 bytes
 - :code:`MB` - megabyte - 1000 kilobytes or 1 000 000 bytes
 - :code:`GB` - gigabyte - 1000 megabytes or 1 000 000 000 bytes
 - :code:`KiB` - kibibyte - 1024 bytes
 - :code:`MiB` - mebibyte - 1024 kibibytes or 1 048 576 bytes
 - :code:`GiB` - gibibyte - 1024 mebibytes or 1 073 741 824 bytes

The suffix must be separated from the number by a space. For example:
:code:`size: 4 MiB` defines the size of 4 mebibytes or 4 194 304 bytes.

On the `sparse` option
^^^^^^^^^^^^^^^^^^

Almost all block descriptions support boolean :code:`sparse` option,
which is enabled by default. You can disable it to generate
non-sparse parts of the resulting images. This will create images that
are bigger while stored on disk, because they physically store all
non-needed NUL regions. But this may be used in cases when you need to
zero out some regions on flash storage. Bear in mind that in this
case, you can't write the result image with

.. code-block:: yaml

    dd of=image.img of=/dev/outdevce conv=sparse

because with :code:`conv=sparse` option :code:`dd` will "un-sparse"
the image file, effectively skipping big zeroed regions. So, you
either need to remove :code:`conv=sparse` option when calling
:code:`dd`, increasing writing time significantly, or use
:code:`bmaptool` which should be less aggressive with sparsed regions
detection.

Empty block
^^^^^^^^^^^

An empty block is a block that does not contain any file or
raw image. `rouge` will write nothing into this block if
:code:`filled: zeroes` option is not specified.

.. code-block:: yaml

   type: empty # defines empty block
   size: 4096
   filled: zeroes

:code:`size` is mandatory, as `rouge` can't infer it.

:code:`filled` is optional, with only `zeroes` value allowed for now.
This option may be used if you need the block to be filled with zeroes.
For example, this is used for some Android partitions, like 'rpmbemul'.
You can use this option only if absolutely necessary. Otherwise, you will
needlessly increase the size and upload time of an image.

.. _rouge-raw-image-block:

Raw Image Block
^^^^^^^^^^^^^^^

The purpose of this block type is to include any binary data from another
file. For example, if your build system creates a `.ext4` image with
the root file system, you can use this block to place that image into a GPT
partition (which is described below).

.. code-block:: yaml

   type: raw_image # defines raw image block
   size: 400 MiB
   resize: false
   image_path: "some/path/rootfs.ext4"

:code:`image_path` is mandatory. This is a file to be included in
resulting image.

:code:`size` is optional. If it is omitted, `rouge` will use the size of
the file. If provided :code:`size` is smaller than file size, `rouge` will
stop with an error. If provided :code:`size` is bigger than file size,
`rouge` will try to resize the file to match :code:`size`. This rule
applies to ext2..ext4 format now.
Note that host tools perform resizing, and you may meet some
compatibility issues if the newer tools generate the ext4 image.
For example, if the ext4 image is generated by the yocto scarthgap
with e2fsprogs 1.47, then such an image can be resized only on the host
with Ubuntu 23+. The lower versions of Ubuntu have e2fsprogs that
can't resize such an image.

:code:`resize` is optional. If set to :code:`false`, it will prevent
`rouge` from resizing the image to the size of the block. This is
useful when you want to include a file that is smaller than the block
and leave the rest of the block empty.

:code:`sparse` is optional. If it is set to to :code:`false`, the raw image
will be copied in non-sparse mode. This may increase the final image
size on disk and processing time. Use this option only when absolutely
necessary, i.e, when some piece of software (like a bootloader) depends
on values in unallocated sectors.

Android Sparse Image Block
^^^^^^^^^^^^^^^^^^^^^^^^^^

It is similar to :ref:`rouge-raw-image-block`, but it handles files in
Android Sparse image format.

.. code-block:: yaml

   type: android_sparse # defines android sparse block
   size: 3000 MiB
   image_path: "android/out/target/product/xenvm/userdata.img"

:code:`image_path` is mandatory. This is a file to be included in
the resulting image. `rouge` will call :code:`simg2img2` tool to
unpack it before writing it to a resulting image.

:code:`size` is optional. If it is omitted, `rouge` will use the data
size read from the file. If provided :code:`size` is smaller than
read size, `rouge` will stop with an error. Thus, you can create a block
that is bigger than the unpacked file, but not smaller.

:code:`sparse` is optional. If it is set to :code:`false`, Android
sparsed image will be completely unsparsed, up to creating a fully
mapped file. It is seldom used, but it is added for completeness.

Filesystem Image With Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This block type allows you to create a new filesystem with some
files included from your disk. This is ideal for creating boot
partitions, where you store the kernel, initial ramdisk, and so on.

.. code-block:: yaml

   type: ext4 # defines ext4 partition block
   size: 30 MiB
   items:
     "remote_file1": "path/to/local/file1"
     "remote_file2": "path/to/local/file2"
     "remote_file3": "path/to/local/file3"
     "remote_file4": "path/to/local/file4"
     "remote_dir": "path/to/local/directory/"

:code:`type` is required. Defines the filesystem type,
currently `ext4` and `vfat` are supported.
You need to install the `mtools` package to work with `vfat`.

:code:`items:` section is optional. It defines :code:`remote:local`
mapping of files that should be presented on the newly created
filesystem. :code:`remote` part is how the file will be named on the new
filesystem, while :code:`local` is a path on your disk.
You can specify parent folders for :code:`remote` and these folders
will be created on the destination filesystem.
You may specify not only files but also directories. If the local
directory contains subdirectories, they will be created under the
:code:`remote` directory.
Older versions of `rouge` used :code:`files:` as the name of the
section. This name is still possible to use, but it is deprecated.
Also, only :code:`items:` can contain directories.

:code:`size` is optional. `rouge` will calculate the total file size and
add some space for the filesystem metadata to determine the block size.
You can increase the size if you wish.

:code:`sparse` is optional. If it is set to :code:`false`, the filesystem
image will be copied in non-sparse mode. This may increase the final image
size on disk and processing time. Use this option only when absolutely
necessary, i.e, when some piece of software (like a bootloader) depends
on values in unallocated sectors.

GUID Partition Table (GPT) block
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This block type defines GPT along with all partitions. In most cases,
this will be your top-level block definition. It can (and should)
include other blocks, including other GPT. Inner GPT can come in handy
in cases when you are creating an image that holds data for multiple
virtual machines and wish to provide each VM with its own GPT.

.. code-block:: yaml

   type: gpt # defines GPT block
   partitions:
     boot: # partition label
       gpt_type: 21686148-6449-6E6F-744E-656564454649 # BIOS boot partition (kinda...)
       gpt_guid: 8DA63339-0007-60C0-C436-083AC8230900 # Partition GUID
       type: empty
       size: 30 MiB
     rootfs:
       gpt_type: B921B045-1DF0-41C3-AF44-4C6F280D3FAE # Linux aarch64 root
       type: raw_image
       image_path: "rootfs.ext4"

This example defines GPT with two partitions: :code:`boot` and
:code:`rootfs`. :code:`boot` is an empty block and :code:`rootfs`
includes Raw Image block.

:code:`partitions:` section is mandatory. It defines a list of
partitions, where the key is a partition label.

:code:`hybrid_mbr` forces rouge to create a Hybrid MBR instead of
the default Protective MBR. Just so you know, this is an experimental feature,
as different OSes handle Hybrid MBR differently; in other words, this
type of MBR is not standardized and is not guaranteed to work on your
setup. It is mainly added to enable support of older Raspberry PI
models, whose bootloader can't parse GPT. When Hybrid MBR is enabled,
the first three partition entries should contain :code:`mbr_type` property
with MBR Partitions type code. In most cases, you will need
:code:`0x0C` for FAT32 partitions and :code:`0x83` for Linux file
systems.

Each partition contains the definition of another block type plus optional keys:

:code:`gpt_type:` (which we strongly suggest providing) key holds GPT Partition
Type GUID. A list of widely used types can be found on
`Wikipedia <https://en.wikipedia.org/wiki/GUID_Partition_Table#Partition_type_GUIDs>`_,
for example.

:code:`gpt_guid:` key sets the GPT Partition GUID. By default, this GUID is generated
automatically to ensure that every partition in the world would have a unique
identifier. But there are some cases when external software depends on the exact value
of a partition GUID. In such cases, it is possible to hard-code this value. We
strongly recommend not to use this key except for the cases when this is necessary
because, according to page 121 of
`Specification <https://uefi.org/sites/default/files/resources/UEFI_Spec_2_8_final.pdf>`_
the software that makes copies of GPT-formatted disks and partitions must generate
new Unique Partition GUID in each GPT Partition Entry.

:code:`sector_size` is a custom sector size, 512 by default, but some devices
(e.g., fancy flash storage) might have a sector of a different size.
This key allows tuning for such cases.

:code:`mbr_type` is used only when :code:`hybrid_mbr` is set for the
GPT block entry. It corresponds to the MBR partition type byte. A list of
partition types can be found on `Wikipedia
<https://en.wikipedia.org/wiki/Partition_type>`_.

`rouge` will place partitions one after another, aligning each partition
start at 1 MiB (as per standard recommendation) and partition size to
sector size, which defaults to 512 bytes.

Examples
--------

The following example provides multiple different images:

.. code-block:: yaml

   min_ver: 0.3
   desc: "rouge sample images"

   images:
     empty_image:
       desc: "Just empty 32MB file"
       type: empty
       size: 32 MiB

     unpacked_userdata:
       desc: "Unpacked Android userspace image"
       type: android_sparse
       image_path: "android/out/target/product/xenvm/userdata.img"

     simple_bootable_sd:
       type: gpt
       desc: "Full SD-card/eMMC image"
       partitions:
         boot:
           gpt_type: 21686148-6449-6E6F-744E-656564454649 # BIOS boot partition (kinda...)
           type: ext4
           size: 30 MiB
           items:
             "Image": "yocto/build/tmp/deploy/images/generic-armv8-xt/Image"
             "initrd": "yocto/build/tmp/deploy/images/generic-armv8-xt/uInitrd"
         domd_rootfs:
           gpt_type: B921B045-1DF0-41C3-AF44-4C6F280D3FAE # Linux aarch64 root
           gpt_guid: 8DA63339-0007-60C0-C436-083AC8230900 # Partition GUID
           type: raw_image
           image_path: "yocto/build-domd/tmp/deploy/images/machine/core-image-weston.ext4"

..

 - :code:`rouge sample_images.yaml -i empty_image` will generate just
   an empty file. This is the simplest example.
 - :code:`rouge sample_images.yaml -i unpacked_userdata` will use
   `simg2img` to unpack Android userdata image.
 - :code:`rouge sample_images.yaml -i unpacked_userdata` will generate
   a sort of usable image with two GPT partitions: one with data for
   the bootloader, and the other will contain an ext4 root image created by Yocto.
