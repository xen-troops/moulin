import unittest
from unittest.mock import patch, Mock
import moulin.builders.yocto as yocto_mod
from pathlib import Path


class TestYoctoUtilitySyncLayers(unittest.TestCase):
    def test_first_run_no_stamp_calls_add_layer(self):
        """
        First run (stamp file does not exist):
        - correct list of layers is passed to "bitbake-layers add-layer"
        - stamp file is updated via "touch"
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # stamp file does not exist -> return_value=False
        with patch("moulin.builders.yocto.Path.exists", return_value=False), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            yocto_mod.handle_utility_call(
                conf=None,
                argv=[
                    "--yocto-dir", yocto_dir,
                    "--work-dir", work_dir,
                    "--layers", *layers,
                    "--stamp", stamp_path,
                ],
            )

        # check command is not None
        self.assertIsNotNone(mock_run.call_args)

        # take the command passed to _run_bash
        cmd = mock_run.call_args[0][0]

        # cmd contains bitbake-layers add-layer and all layers
        self.assertIn("bitbake-layers add-layer", cmd)
        for layer in layers:
            self.assertIn(layer, cmd)

        # stamp file was updated
        self.assertIn(f"touch {stamp_path}", cmd)

    def test_stamp_exists_sync_layers(self):
        """
        Stamp exists:
        - unneeded layer removed (ABS path)
        - needed layers added (ABS paths)
        - stamp updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # -> this one is *not* in layers and must be removed
        unneeded_rel = "../current-fake-layer"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]
        unneeded_abs = str((build_abs / unneeded_rel).resolve(strict=False))

        # Realistic show-layers output: 3 Yocto core layers + one unneeded managed layer
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"meta   {unneeded_abs} 5\n"
        )

        # stamp exist -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> apply diff
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
                conf=None,
                argv=[
                    "--yocto-dir", yocto_dir,
                    "--work-dir", work_dir,
                    "--layers", *layers,
                    "--stamp", stamp_path,
                ],
            )

        # check command is not None
        self.assertIsNotNone(mock_run.call_args)

        # take the command passed to _run_bash
        cmd = mock_run.call_args[0][0]

        # check remove-layer segment
        self.assertIn("bitbake-layers remove-layer", cmd)
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]
        # unneeded_abs must be present in remove
        self.assertIn(unneeded_abs, rm_seg, msg=f"{unneeded_abs} \
            not found in remove-layer segment:\n{rm_seg}")

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # all layers_abs must be in add-layer
        for p in layers_abs:
            self.assertIn(p, add_seg, msg=f"{p} not found in add-layer segment:\n{add_seg}")
        # there shouldn't be unneeded_abs there
        self.assertNotIn(unneeded_abs, add_seg, msg=f"{unneeded_abs} \
            must NOT be in add-layer segment:\n{add_seg}")

        # stamp file was updated
        self.assertIn(f"touch {stamp_path}", cmd)
