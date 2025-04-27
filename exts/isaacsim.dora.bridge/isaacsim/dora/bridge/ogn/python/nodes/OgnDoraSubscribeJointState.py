"""
OmniGraph core Python API:
  https://docs.omniverse.nvidia.com/kit/docs/omni.graph/latest/Overview.html

OmniGraph attribute data types:
  https://docs.omniverse.nvidia.com/kit/docs/omni.graph.docs/latest/dev/ogn/attribute_types.html

Collection of OmniGraph code examples in Python:
  https://docs.omniverse.nvidia.com/kit/docs/omni.graph.docs/latest/dev/ogn/ogn_code_samples_python.html

Collection of OmniGraph tutorials:
  https://docs.omniverse.nvidia.com/kit/docs/omni.graph.tutorials/latest/Overview.html
"""

# Copyright (c) 2022-2024, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import omni
from pxr import Usd
import carb
import omni.syntheticdata._syntheticdata as sd
from omni.replicator.core import AnnotatorRegistry, Writer
import numpy as np
import traceback
from isaacsim.core.nodes import BaseWriterNode
import omni.replicator.core as rep
from multiprocessing import shared_memory
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
import pickle


class OgnDoraSubscribeJointStateInternalState(BaseWriterNode):
    """Convenience class for maintaining per-node state information"""

    def __init__(self):
        """Instantiate the per-node state information"""
        self.robot_prim = None
        self.controller_handle = None
        self.dof_indices = None
        self.shm = None
        super().__init__(initialize = False)
    
    def initialize_controller_shm(self, sharedMemName):
        self.controller_handle = SingleArticulation(self.robot_prim)
        self.controller_handle.initialize()
        dof_names = self.controller_handle.dof_names
        self.dof_indices = np.array([self.controller_handle.get_dof_index(name) for name in dof_names])

        self.shm = shared_memory.SharedMemory(name=sharedMemName, create=False)


class OgnDoraSubscribeJointState:
    """The Ogn node class"""

    @staticmethod
    def internal_state():
        """Returns an object that contains per-node state information"""
        return OgnDoraSubscribeJointStateInternalState()

    @staticmethod
    def compute(db) -> bool:
        state = db.per_instance_state
        if not state.initialized:
            if len(db.inputs.targetPrim) == 0:
                db.log_error("No robot prim found for the articulation controller")
                return False
            else:
                state.robot_prim = db.inputs.targetPrim[0].GetString()
            state.initialize_controller_shm(db.inputs.sharedMemName)
            state.initialized = True
        
        # positions = pickle.loads(state.shm.buf)
        # print(positions)
        # db.outputs.positionCommand = positions
        data = pickle.loads(state.shm.buf)
        if data is not None:
            joint_actions = ArticulationAction()
            joint_actions.joint_indices = state.dof_indices
            joint_actions.joint_positions = data
            state.controller_handle.apply_action(control_actions=joint_actions)
        return True

