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
from isaacsim.gui.components.ui_utils import get_style, dropdown_builder, int_builder, btn_builder
from isaacsim.gui.components.element_wrappers import CollapsableFrame
from isaacsim.gui.components.callbacks import on_copy_to_clipboard
from omni.kit.window.property.templates import LABEL_HEIGHT, LABEL_WIDTH
from omni.usd import StageEventType
from pxr import Sdf, UsdLux
import pyperclip
import cv2

from .scenario import FrankaRmpFlowExampleScript


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

class UIBuilder:
    def __init__(self):
        # Frames are sub-windows that can contain multiple UI elements
        self.frames = []
        # UI elements created using a UIElementWrapper instance
        self.wrapped_ui_elements = []

        # Get access to the timeline to control stop/pause/play programmatically
        self._timeline = omni.timeline.get_timeline_interface()

        # Run initialization for the provided example
        self._on_init()

        self._camera_path_checkbox_list = ["1", "2", "3"]
        self._dora_node_info = ""

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
        if event.type == int(omni.timeline.TimelineEventType.STOP):
            # When the user hits the stop button through the UI, they will inevitably discover edge cases where things break
            # For complete robustness, the user should resolve those edge cases here
            # In general, for extensions based off this template, there is no value to having the user click the play/stop
            # button instead of using the Load/Reset/Run buttons provided.
            self._scenario_state_btn.reset()
            self._scenario_state_btn.enabled = False

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
        if event.type == int(StageEventType.OPENED):
            # If the user opens a new stage, the extension should completely reset
            self._reset_extension()

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
                self._camera_path_checkbox = dropdown_builder(
                    label = "Camera Path", 
                    items = self._camera_path_checkbox_list, 
                    tooltip = "Select A Camera In Stage", 
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
                    on_clicked_fn = lambda: self.generate_dora_node(), 
                )

                self._dora_node_scrolling_frame = higher_scrolling_frame_builder(
                    label = "Dora Node", 
                    default_val = self._dora_node_info, 
                )

                self._test_btn = btn_builder(
                    label = "", 
                    text = "Test", 
                    on_clicked_fn = lambda: self._test(), 
                )
    
    def generate_dora_node(self):
        publish_rate = self._publish_rate_field.get_value_as_int()
        millis = int(1000 / publish_rate)
        self._dora_node_scrolling_frame.text = f"""- id: dora_isaacsim_camera_publisher\n  operator: \n    python: publish.py\n    inputs: \n      tick: dora/timer/millis/{str(millis)}\n    outputs: \n      - image"""

    def _test():
        pass

    ######################################################################################
    # Functions Below This Point Support The Provided Example And Can Be Deleted/Replaced
    ######################################################################################

    def _on_init(self):
        self._articulation = None
        self._cuboid = None
        self._scenario = FrankaRmpFlowExampleScript()

    def _reset_extension(self):
        """This is called when the user opens a new stage from self.on_stage_event().
        All state should be reset.
        """
        self._on_init()
        self._reset_ui()

    def _reset_ui(self):
        self._scenario_state_btn.reset()
        self._scenario_state_btn.enabled = False
        self._reset_btn.enabled = False
