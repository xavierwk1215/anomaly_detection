import numpy as np
from onnxruntime import InferenceSession
import cv2 as cv
from src.models.detection.detector_base import DetectorBase, Model
from src.models.base.yolov8_base import ModelError
from src.utils.boxes import xywh2xyxy, multiclass_nms_class_agnostic
from src.utils.general import get_classes


class Yolov8Detector(DetectorBase):
    def __init__(self):
        self._model = None

    def init(self, model_path, confidence_threshold=0.3, iou_threshold=0.45):
        _session = InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_names, self.output_names, input_size = self.get_onnx_model_details(_session)
        self._model = Model(
            model=_session,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size
        )
        init_frame = np.random.randint(0, 256, (input_size[0], input_size[1], 3)).astype(np.uint8)
        self.inference(init_frame)
    
    def postprocess(self, model_output, scale, conf_threshold, iou_threshold, class_names):
        predictions = np.squeeze(model_output[0]).T
        scores = np.max(predictions[:, 4:], axis=1)
        predictions = predictions[scores > conf_threshold, :]
        scores = scores[scores > conf_threshold]
        if len(scores) == 0:
            return []
        boxes = predictions[:, :4]
        boxes = xywh2xyxy(boxes)
        boxes *= scale
        dets = multiclass_nms_class_agnostic(boxes, predictions[:, 4:], iou_threshold, conf_threshold)
        detection_results=[]
        i=0
        for det in dets:
            obj_dict = {
                    "id": int(i),
                    'class': class_names[int(det[5])],
                    'confidence': det[4],
                    'bbox': np.rint(det[:4]),
                    "keypoints":[],
                    "segmentation":[]}
            detection_results.append(obj_dict)
            i += 1
        return detection_results

    def inference(self, image, confi_thres=None, iou_thres=None):
        if self._model is None:
            raise ModelError("Model not initialized. Have you called init()?")
        if confi_thres is None:
            confi_thres = self._model.confidence_threshold
        if iou_thres is None:
            iou_thres = self._model.iou_threshold

        scale, image = self.preprocess(image, self._model.input_size)

        ort_inputs = {self.input_names[0]: image}
        outputs = self._model.model.run(self.output_names, ort_inputs)

        detection_results = self.postprocess(
            model_output=outputs,
            scale=scale,
            conf_threshold=confi_thres,
            iou_threshold=iou_thres,
            class_names=self._model.class_names
        )
        return detection_results
