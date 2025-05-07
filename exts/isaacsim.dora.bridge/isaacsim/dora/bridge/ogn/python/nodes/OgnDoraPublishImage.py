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
import carb
import omni
from omni.replicator.core import AnnotatorRegistry, Writer
import numpy as np
from isaacsim.core.nodes import BaseWriterNode
import omni.replicator.core as rep
from multiprocessing import shared_memory
import pickle
from isaacsim.dora.bridge.ogn.OgnDoraPublishImageDatabase import OgnDoraPublishImageDatabase

# modify from PytorchWriter in isaacsim.replicator.writers
class DoraImageWriter(Writer):
    """A custom writer that uses omni.replicator API to retrieve RGB data via render products.
    """

    def __init__(self):
        self._frame_id = 0
        self.annotators = [AnnotatorRegistry.get_annotator("LdrColor", device="cuda", do_array_copy=False)]
        self.image_data = None

    def write(self, data: dict) -> None:
        for annotator in data.keys():
            if annotator.startswith("LdrColor") or annotator.startswith("RtxSensor"):
                self.image_data = np.transpose(data[annotator].numpy()[:, :, :3], (1, 0, 2))
                break
        self._frame_id += 1

    def get_image_data(self):
        return self.image_data


class OgnDoraPublishImageInternalState(BaseWriterNode):
    """Convenience class for maintaining per-node state information"""

    def __init__(self):
        """Instantiate the per-node state information"""
        self.handle = None
        self.dora_image_writer = None
        self.shm = None
        super().__init__(initialize = False)
    
    def on_stage_event(self, event: carb.events.IEvent):
        if event.type == int(omni.timeline.TimelineEventType.STOP):
            if self.handle:
                self.handle.hydra_texture.set_updates_enabled(False)
            self.initialized = False
        elif event.type == int(omni.timeline.TimelineEventType.PLAY):
            if self.handle:
                self.handle.hydra_texture.set_updates_enabled(True)
    
    def set_param(self, cameraPrim, cameraWidth, cameraHeight, sharedMemName):
        try:
            exist_shm = shared_memory.SharedMemory(name = sharedMemName)
            exist_shm.close()
            exist_shm.unlink()
        except:
            pass
        size = cameraWidth * cameraHeight * 3 * 8
        self.shm = shared_memory.SharedMemory(name=sharedMemName, create=True, size=size)
        
        self.dora_image_writer = DoraImageWriter()
        self.handle = rep.create.render_product(
            cameraPrim, (cameraWidth, cameraHeight), force_new = True
        )
        # self.handle.hydra_texture.set_updates_enabled(True)
        try:
            self.dora_image_writer.attach(self.handle)
        except:
            self.dora_image_writer.detach()
            self.handle.destroy()
            return
        self.initialized = True

class OgnDoraPublishImage:
    """The Ogn node class"""

    @staticmethod
    def internal_state():
        """Returns an object that contains per-node state information"""
        return OgnDoraPublishImageInternalState()

    @staticmethod
    def compute(db) -> bool:
        state = db.per_instance_state
        if not state.initialized:
            state.set_param(db.inputs.cameraPrim[0].GetString(), db.inputs.cameraWidth, db.inputs.cameraHeight, db.inputs.sharedMemName)
        # write into shm
        else:
            image_data = state.dora_image_writer.get_image_data()
            if image_data is not None:
                image_data = image_data.reshape(-1).tolist()
                image_data = pickle.dumps(image_data)
                db.per_instance_state.shm.buf[:len(image_data)] = image_data
                
                # data_array = np.ndarray(image_data.shape, dtype=image_data.dtype, buffer=state.shm.buf)
                # data_array[:] = image_data
        return True
    
    @staticmethod
    def release_instance(node, graph_instance_id):
        try:
            state = OgnDoraPublishImageDatabase.per_instance_internal_state(node)
        except Exception:
            state = None
            pass

        if state is not None:
            try:
                state.dora_image_writer.detach()
            except:
                pass
            if state.handle:
                state.handle.destroy()
            state.handle = None

