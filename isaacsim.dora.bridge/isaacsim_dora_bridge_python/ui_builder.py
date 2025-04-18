# Copyright (c) 2022-2024, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import omni.timeline
import omni.ui as ui
from isaacsim.core.api.world import World
from isaacsim.core.prims import SingleXFormPrim
from isaacsim.core.utils.stage import create_new_stage, get_current_stage
from isaacsim.gui.components.ui_utils import get_style, dropdown_builder, int_builder, str_builder, btn_builder, state_btn_builder
from isaacsim.gui.components.element_wrappers import CollapsableFrame
from isaacsim.gui.components.callbacks import on_copy_to_clipboard
from omni.kit.window.property.templates import LABEL_HEIGHT, LABEL_WIDTH
from omni.usd import StageEventType
from pxr import Sdf, UsdLux
import cv2
from omni.isaac.core.utils.stage import open_stage
from omni.isaac.core.utils.prims import get_prim_at_path
import os
from isaacsim.replicator.writers import PytorchListener, PytorchWriter
import asyncio
import json
import omni.replicator.core as rep
from multiprocessing import shared_memory
import numpy as np
import time
from typing import Optional
import torch
import carb
import warp as wp
from omni.replicator.core import AnnotatorRegistry, BackendDispatch, Writer


def higher_scrolling_frame_builder(label="", type="scrolling_frame", default_val="No Data", tooltip=""):
    """Creates a Labeled Scrolling Frame with CopyToClipboard button

    Args:
        label (str, optional): Label to the left of the UI element. Defaults to "".
        type (str, optional): Type of UI element. Defaults to "scrolling_frame".
        default_val (str, optional): Default Text. Defaults to "No Data".
        tooltip (str, optional): Tooltip to display over the Label. Defaults to "".

    Returns:
        ui.Label: label
    """

    with ui.VStack(style=get_style(), spacing=5):
        with ui.HStack():
            ui.Label(label, width=LABEL_WIDTH, alignment=ui.Alignment.LEFT_TOP, tooltip="")
            with ui.ScrollingFrame(
                height=LABEL_HEIGHT * 7,
                style_type_name_override="ScrollingFrame",
                alignment=ui.Alignment.LEFT_TOP,
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON,
            ):
                text = ui.Label(
                    default_val,
                    style_type_name_override="Label::label",
                    word_wrap=True,
                    alignment=ui.Alignment.LEFT_TOP,
                )
            with ui.Frame(width=0, tooltip="Copy To Clipboard"):
                ui.Button(
                    name="IconButton",
                    width=20,
                    height=20,
                    clicked_fn=lambda: pyperclip.copy("text.text"),
                    style=get_style()["IconButton.Image::CopyToClipboard"],
                    alignment=ui.Alignment.RIGHT_TOP,
                )
    return text


class DoraRGBListener:
    """A Observer/Listener that keeps track of updated data sent by the writer. Is passed in the
    initialization of a PytorchWriter at which point it is pinged by the writer after any data is
    passed to the writer."""

    def __init__(self):
        self.data = {}

    def write_data(self, data: dict) -> None:
        """Updates the existing data in the listener with the new data provided.

        Args:
            data (dict): new data retrieved from writer.
        """

        self.data.update(data)

    def get_rgb_data(self) -> Optional[torch.Tensor]:
        """Returns RGB data as a batched tensor from the current data stored.

        Returns:
            images (Optional[torch.Tensor]): images in batched pytorch tensor form
        """

        if "pytorch_rgb" in self.data:
            images = self.data["pytorch_rgb"]
            images = images[..., :3]
            images = images.permute(0, 3, 1, 2)
            return images
        else:
            return None


class DoraRGBWriter(Writer):
    """A custom writer that uses omni.replicator API to retrieve RGB data via render products
        and formats them as tensor batches. The writer takes a PytorchListener which is able
        to retrieve pytorch tensors for the user directly after each writer call.

    Args:
        listener (PytorchListener): A PytorchListener that is sent pytorch batch tensors at each write() call.
        output_dir (str): directory in which rgb data will be saved in PNG format by the backend dispatch.
                          If not specified, the writer will not write rgb data as png and only ping the
                          listener with batched tensors.
        device (str): device in which the pytorch tensor data will reside. Can be "cpu", "cuda", or any
                      other format that pytorch supports for devices. Default is "cuda".
    """

    def __init__(
        self, listener: DoraRGBListener, output_dir: str = None, tiled_sensor: bool = False, device: str = "cuda"
    ):
        # If output directory is specified, writer will write annotated data to the given directory
        if output_dir:
            self.backend = BackendDispatch({"paths": {"out_dir": output_dir}})
            self._backend = self.backend
            self._output_dir = self.backend.output_dir
        else:
            self._output_dir = None
        self._frame_id = 0

        if tiled_sensor:
            self.annotators = [AnnotatorRegistry.get_annotator("RtxSensorGpu", device="cuda", do_array_copy=False)]
        else:
            self.annotators = [AnnotatorRegistry.get_annotator("LdrColor", device="cuda", do_array_copy=False)]

        self.listener = listener
        self.device = device

    def write(self, data: dict) -> None:
        """Sends data captured by the attached render products to the PytorchListener and will write data to
        the output directory if specified during initialization.

        Args:
            data (dict): Data to be pinged to the listener and written to the output directory if specified.
        """
        # breakpoint()
        for annotator in data.keys():
            if annotator.startswith("rp"):
                rp_info = data[annotator]

        if self._output_dir:
            # Write RGB data to output directory as png
            self._write_rgb(data, rp_info)
        pytorch_rgb = self._convert_to_pytorch(data, rp_info).to(self.device)
        self.listener.write_data({"pytorch_rgb": pytorch_rgb, "device": self.device})
        self._frame_id += 1

    @carb.profiler.profile
    def _write_rgb(self, data: dict, rp_info: dict) -> None:
        for annotator in data.keys():
            if annotator.startswith("LdrColor"):
                render_product_name = annotator.split("-")[-1]
                file_path = f"rgb_{self._frame_id}_{render_product_name}.png"
                img_data = data[annotator]
                if isinstance(img_data, wp.types.array):
                    img_data = img_data.numpy()
                self._backend.write_image(file_path, img_data)
            elif annotator.startswith("RtxSensor"):
                width, height = rp_info["resolution"][0], rp_info["resolution"][1]
                file_path = f"rgb_{self._frame_id}.png"
                img_data = data[annotator].reshape(height, width, -1)
                self._backend.write_image(file_path, img_data)

    @carb.profiler.profile
    def _convert_to_pytorch(self, data: dict, rp_info: dict) -> torch.Tensor:
        if data is None:
            raise Exception("Data is Null")
        # breakpoint()
        data_tensors = []
        for annotator in data.keys():
            if annotator.startswith("LdrColor"):
                data_tensors.append(wp.to_torch(data[annotator]).unsqueeze(0))
            elif annotator.startswith("RtxSensor"):
                breakpoint()
                width, height = rp_info["resolution"][0], rp_info["resolution"][1]
                img_data = data[annotator]
                data_tensors.append(wp.to_torch(img_data).reshape(height, width, -1).unsqueeze(0))
            elif annotator.startswith("distance"):
                width, height = rp_info["resolution"][0], rp_info["resolution"][1]
                data_tensors.append(wp.to_torch(data[annotator]).reshape(height, width, -1).unsqueeze(0))

        # Move all tensors to the same device for concatenation
        device = "cuda:0" if self.device == "cuda" else self.device
        data_tensors = [t.to(device) for t in data_tensors]

        data_tensor = torch.cat(data_tensors, dim=0)
        return data_tensor


class UIBuilder:
    def __init__(self):
        # Frames are sub-windows that can contain multiple UI elements
        self.frames = []
        # UI elements created using a UIElementWrapper instance
        self.wrapped_ui_elements = []

        # Get access to the timeline to control stop/pause/play programmatically
        self._timeline = omni.timeline.get_timeline_interface()

        self.camera_path = ""
        self.camera_width = 640
        self.camera_height = 480
        self.publish_rate = 5
        self.interval_millis = 200

        # self._camera_path_checkbox_list = ["1", "2", "3"]
        # self._selected_camera_path_index = 0

        self._dora_node_info = ""
        self.publish = False

    ###################################################################################
    #           The Functions Below Are Called Automatically By extension.py
    ###################################################################################

    def on_menu_callback(self):
        """Callback for when the UI is opened from the toolbar.
        This is called directly after build_ui().
        """
        pass

    def on_timeline_event(self, event):
        """Callback for Timeline events (Play, Pause, Stop)

        Args:
            event (omni.timeline.TimelineEventType): Event Type
        """
        pass

    def on_physics_step(self, step: float):
        """Callback for Physics Step.
        Physics steps only occur when the timeline is playing

        Args:
            step (float): Size of physics step
        """
        pass

    def on_stage_event(self, event):
        """Callback for Stage Events

        Args:
            event (omni.usd.StageEventType): Event Type
        """
        # if event.type == int(StageEventType.OPENED):
            # If the user opens a new stage, the extension should completely reset
            # self._reset_extension()
        pass

    def cleanup(self):
        """
        Called when the stage is closed or the extension is hot reloaded.
        Perform any necessary cleanup such as removing active callback functions
        Buttons imported from isaacsim.gui.components.element_wrappers implement a cleanup function that should be called
        """
        for ui_elem in self.wrapped_ui_elements:
            ui_elem.cleanup()

    def build_ui(self):
        """
        Build a custom UI tool to run your extension.
        This function will be called any time the UI window is closed and reopened.
        """
        dora_setting_frame = CollapsableFrame("Dora Setting", collapsed=False)

        with dora_setting_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                # self._camera_path_checkbox = dropdown_builder(
                #     label = "Camera Path", 
                #     items = self._camera_path_checkbox_list, 
                #     tooltip = "Select A Camera In Stage", 
                #     on_clicked_fn = self.on_camera_path_changed, 
                # )
                self._camera_path_field = str_builder(
                    label = "Camera Path", 
                    default_val = "/World/Camera", 
                    tooltip = "Camera Path", 
                )

                self._camera_width_field = int_builder(
                    label = "Camera Width", 
                    default_val = 640, 
                    tooltip = "Camera Width", 
                )

                self._camera_height_field = int_builder(
                    label = "Camera Height", 
                    default_val = 480, 
                    tooltip = "Camera Height", 
                )

                self._publish_rate_field = int_builder(
                    label = "Publish Rate", 
                    default_val = 5, 
                    tooltip = "Publish Rate", 
                )

                self._generate_dora_node_btn = btn_builder(
                    label = "", 
                    text = "Generate Dora Node", 
                    tooltip = "Generate Dora Node", 
                    on_clicked_fn = self.generate_dora_node, 
                )

                self._dora_node_scrolling_frame = higher_scrolling_frame_builder(
                    label = "Dora Node", 
                    default_val = self._dora_node_info, 
                )

                self._start_btn = state_btn_builder(
                    label = "", 
                    a_text = "Start", 
                    b_text = "Stop", 
                    tooltip = "Start Or Stop", 
                    on_clicked_fn = asyncio.ensure_future(self.reverse_publish), 
                )
    
    ######################################################################################
    # Functions Below This Point Support The Provided Example And Can Be Deleted/Replaced
    ######################################################################################
    async def reverse_publish(self, val):
        self.publish = val
        if val:
            size = self.camera_width * self.camera_height * 4
            shm = shared_memory.SharedMemory(name="isaacsim_dora_bridge_rgb", create=True, size=size)
            interval_seconds = self.interval_millis / 1000
            try:
                data_array = np.ndarray((1,), dtype=np.int64, buffer=shm.buf)
                rp = rep.create.render_product(
                    self.camera_path, (self.camera_width, self.camera_height), force_new = True
                )
                dora_rgb_listener = DoraRGBListener()
                dora_rgb_writer = DoraRGBWriter(dora_rgb_listener)
                dora_rgb_writer.attach(rp)
                while self.publish:
                    await rep.orchestrator.step_async()
                    data_array[0] = dora_rgb_writer.listener.get_rgb_data()
                    time.sleep(interval_seconds)
            finally:
                shm.close()
                shm.unlink()
                dora_rgb_writer.detach()
                rp.destroy()
                await rep.orchestrator.wait_until_complete_async()


    def generate_dora_node(self):
        self.camera_path = self._camera_path_field.get_value_as_string()
        self.camera_width = self._camera_width_field.get_value_as_int()
        self.camera_height = self._camera_height_field.get_value_as_int()
        camera_cfg = {
            "path": self.camera_path, 
            "width": self.camera_width, 
            "height": self.camera_height
        }
        file_path = os.path.abspath(__file__)
        dir_path = os.path.dirname(file_path)
        camera_cfg_file_path = dir_path + "/camera_cfg.json"
        with open(camera_cfg_file_path, "w", encoding="utf-8") as f:
            json.dump(camera_cfg, f, ensure_ascii=False, indent = 4)
        self.publish_rate = self._publish_rate_field.get_value_as_int()
        publisher_path = dir_path + "rgb_publisher.py"
        self.interval_millis = int(1000 / self.publish_rate)
        self._dora_node_scrolling_frame.text = f"""- id: dora_isaacsim_camera_publisher\n  operator: \n    python: {publisher_path}\n    inputs: \n      tick: dora/timer/millis/{str(interval_millis)}\n    outputs: \n      - image"""

    

# writer = rep.writers.get("BasicWriter")
# print(f"Output directory: {out_dir}")
# writer.initialize(output_dir = out_dir, rgb = True)
# writer.attach(rp)
# for i in range(3):
#     print(f"Step {i}")
#     rep.orchestrator.step_async()
# writer.detach()
# rp.destroy()
# rep.orchestrator.wait_until_complete_async()
