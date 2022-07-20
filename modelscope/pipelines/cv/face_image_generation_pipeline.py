import os
from typing import Any, Dict

import cv2
import numpy as np
import PIL
import torch

from modelscope.metainfo import Pipelines
from modelscope.models.cv.face_generation import stylegan2
from modelscope.outputs import OutputKeys
from modelscope.pipelines.base import Input
from modelscope.preprocessors import load_image
from modelscope.utils.constant import ModelFile, Tasks
from modelscope.utils.logger import get_logger
from ..base import Pipeline
from ..builder import PIPELINES

logger = get_logger()


@PIPELINES.register_module(
    Tasks.image_generation, module_name=Pipelines.face_image_generation)
class FaceImageGenerationPipeline(Pipeline):

    def __init__(self, model: str):
        """
        use `model` and `preprocessor` to create a kws pipeline for prediction
        Args:
            model: model id on modelscope hub.
        """
        super().__init__(model=model)
        self.size = 1024
        self.latent = 512
        self.n_mlp = 8
        self.channel_multiplier = 2
        self.truncation = 0.7
        self.truncation_mean = 4096
        self.generator = stylegan2.Generator(
            self.size,
            self.latent,
            self.n_mlp,
            channel_multiplier=self.channel_multiplier)

        self.model_file = f'{model}/{ModelFile.TORCH_MODEL_FILE}'

        self.generator.load_state_dict(torch.load(self.model_file)['g_ema'])
        logger.info('load model done')

        self.mean_latent = None
        if self.truncation < 1:
            with torch.no_grad():
                self.mean_latent = self.generator.mean_latent(
                    self.truncation_mean)

    def preprocess(self, input: Input) -> Dict[str, Any]:
        return input

    def forward(self, input: Dict[str, Any]) -> Dict[str, Any]:
        assert isinstance(input, int)
        torch.manual_seed(input)
        torch.cuda.manual_seed(input)
        torch.cuda.manual_seed_all(input)
        self.generator.eval()
        with torch.no_grad():
            sample_z = torch.randn(1, self.latent)

            sample, _ = self.generator([sample_z],
                                       truncation=self.truncation,
                                       truncation_latent=self.mean_latent)

            sample = sample * 0.5 + 0.5
            sample = sample.squeeze(0).permute(1, 2, 0).flip(2)  # RGB->BGR
            sample = np.clip(sample.float().cpu().numpy(), 0, 1) * 255

        return {OutputKeys.OUTPUT_IMG: sample.astype(np.uint8)}

    def postprocess(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return inputs
