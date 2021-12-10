from functools import partial
import json
import numpy as np

from .q1core import Q1Core
from .rt_renderer import Renderer

class Q1Sequencer:
    _seq_parameters = [
        # -- handled settings:
        'nco_freq',
        'mod_en_awg',
        'demod_en_acq',
        'channel_map_path0_out0_en',
        'channel_map_path1_out1_en',
        'channel_map_path0_out2_en',
        'channel_map_path1_out3_en',
        'waveforms_and_program',
        # -- only printed:
        'sync_en',
        'nco_phase_offs',
        'marker_ovr_en',
        'marker_ovr_value',
        'cont_mode_en_awg_path0',
        'cont_mode_en_awg_path1',
        'cont_mode_waveform_idx_awg_path0',
        'cont_mode_waveform_idx_awg_path1',
        'upsample_rate_awg_path0',
        'upsample_rate_awg_path1',
        'gain_awg_path0',
        'gain_awg_path1',
        'offset_awg_path0',
        'offset_awg_path1',
        'mixer_corr_phase_offset_degree',
        'mixer_corr_gain_ratio',
        'integration_length_acq',
        'phase_rotation_acq',
        'discretization_threshold_acq',
        ]

    def __init__(self, name):
        self.name = name
        self.reset()

    def reset(self):
        self._mod_en_awg = False
        self._nco_freq = 0.0
        self._demod_en_acq = False

        self.waveforms = {}
        self.weights = {}
        self.acquisition_bins = {}

        self.run_state = 'IDLE'
        self.rt_renderer = Renderer(self.name)
        self.q1core = Q1Core(self.name, self.rt_renderer)

    def __getattr__(self, name):
        if name in self._seq_parameters:
            return partial(self.set, name)

    def set(self, name, value):
        if name == 'name':
            self.name = value
            self.rt_renderer.name = value
        elif name == 'waveforms_and_program':
            self.upload(value)
        elif name == 'mod_en_awg':
            self._mod_en_awg = value
        elif name == 'nco_freq':
            self._nco_freq = value
        elif name == 'demod_en_acq':
            self._demod_en_acq = value
        elif name.startswith('channel_map_path'):
            path = int(name[16])
            out = int(name[21])
            self.rt_renderer.path_enable(path, out, value)
        elif name == 'max_render_time':
            self.rt_renderer.max_render_time = value
        elif name == 'max_core_cycles':
            self.q1core.max_core_cycles = value
        else:
            print(f'{self.name}: {name}={value}')

    def upload(self, file_name):
        with open(file_name) as fp:
            pdict = json.load(fp)
        waveforms = pdict['waveforms']
        weights = pdict['weights']
        acquisitions = pdict['acquisitions']
        program = pdict['program']
        self._set_waveforms(waveforms)
        self._set_weights(weights)
        self._set_acquisition_bins(acquisitions)
        self.q1core.load(program)


    def _set_waveforms(self, waveforms):
        self.waveforms = waveforms
        wavedict = {}
        for name, datadict in waveforms.items():
            index = int(datadict['index'])
            data = np.array(datadict['data'])
            wavedict[index] = data
        self.rt_renderer.set_waveforms(wavedict)

    def _set_weights(self, weights):
        self.weights = weights
        weightsdict = {}
        for name, datadict in weights.items():
            index = int(datadict['index'])
            data = np.array(datadict['data'])
            weightsdict[index] = data
        self.rt_renderer.set_weights(weightsdict)

    def _set_acquisition_bins(self, acq_bins):
        self.acquisition_bins = acq_bins
        bins_dict = {}
        for name, datadict in acq_bins.items():
            index = int(datadict['index'])
            num_bins = int(datadict['num_bins'])
            bins_dict[index] = num_bins
        self.rt_renderer.set_acquisition_bins(bins_dict)

    def get_state(self):
        return {
            'status':self.run_state,
            'flags':list(self.q1core.errors | self.rt_renderer.errors)
            }

    def get_acquisition_state(self):
        return True

    def arm(self):
        self.run_state = 'ARMED'

    def run(self):
        self.run_state = 'RUNNING'
        self.rt_renderer.reset()
        self.rt_renderer.set_nco(self._nco_freq, self._mod_en_awg)
        self.q1core.run()
        self.run_state = 'STOPPED'

    def get_acquisition_data(self):
        cnt,data = self.rt_renderer.get_acquisition_data()
        result = {}
        for name, datadict in self.acquisition_bins.items():
            index = int(datadict['index'])
            num_bins = int(datadict['num_bins'])
            acq_count = cnt[index]
            path_data = data[index]
            result[name] = {
                'index':index,
                'acquisition':{
                    'bins':{
                        'integration': {
                            'path0':path_data,
                            'path1':path_data,
                            },
                        'threshold':[0.0]*num_bins,
                        'avg_cnt':acq_count,
                    }
                }}
        return result

    def plot(self):
        self.rt_renderer.plot()

    def print_registers(self, reg_nrs=None):
        self.q1core.print_registers(reg_nrs)