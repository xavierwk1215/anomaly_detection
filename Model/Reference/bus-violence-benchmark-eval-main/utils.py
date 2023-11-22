
import collections
import os
import random
from pathlib import Path
import re

import numpy as np
import torch


def seed_everything(seed):
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    #torch.use_deterministic_algorithms(True)


def seed_worker(worker_id):
    worker_seed = torch.initial_seed() % 2 ** 32
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    
    
class CheckpointManager:

    def __init__(
        self,
        ckpt_dir,
        ckpt_format=None,
        current_best={},
        metric_modes=None
    ):
        self.ckpt_dir = Path(ckpt_dir)
        self.ckpt_format = ckpt_format if ckpt_format else self._default_ckpt_format
        self.current_best = collections.defaultdict(lambda: None, current_best)
        self.metric_modes = metric_modes if metric_modes else self._default_metric_mode
    
    def save(self, ckpt, metrics, epoch):
        
        ckpt_path = self.ckpt_dir / f'ckpt_e{epoch}.pth'

        for metric, value in metrics.items():
            mode = self.metric_modes(metric)
            if mode == 'ignore':
                continue
            
            cur_best = self.current_best[metric] and self.current_best[metric].get('value', None)
            is_new_best = cur_best is None or ((value <= cur_best) if mode == 'min' else (value >= cur_best))
            if is_new_best:
                if not ckpt_path.exists():  # save ckpt if not already saved
                    torch.save(ckpt, ckpt_path)

                # create a link indicating a best ckpt
                best_metric_ckpt_name = self.ckpt_format(metric, value, epoch)
                best_metric_ckpt_path = self.ckpt_dir / best_metric_ckpt_name
                if best_metric_ckpt_path.exists():
                    best_metric_ckpt_path.unlink()
                best_metric_ckpt_path.symlink_to(ckpt_path.name)

                # update current best
                self.current_best[metric] = {'value': value, 'epoch': epoch}

        self.house_keeping()  # deletes orphan checkpoints
        return dict(self.current_best)
    
    @staticmethod
    def _default_ckpt_format(metric_name, metric_value, epoch):
        metric_name = metric_name.replace('/', '-')
        return f'best_model_metric_{metric_name}.pth'
    
    @staticmethod
    def _default_metric_mode(metric_name):
        if 'accuracy' in metric_name:
            return 'max'
        
        return 'ignore'
    
    def house_keeping(self):
        maybe_ckpts = self.ckpt_dir.glob('ckpt_e*.pth')

        ckpt_re = re.compile(r'ckpt_e\d+\.pth')
        ckpts = filter(lambda p: ckpt_re.match(p.name), maybe_ckpts)
        ckpts = map(lambda p: p.resolve(), ckpts)
        ckpts = set(list(ckpts))

        symlinks = self.ckpt_dir.glob('*.pth')
        symlinks = filter(lambda p: p.is_symlink(), symlinks)
        symlinks = map(lambda p: p.resolve(), symlinks)
        symlinks = set(list(symlinks))

        unused_ckpts = ckpts - symlinks
        for unused_ckpt in unused_ckpts:
            unused_ckpt.unlink()
