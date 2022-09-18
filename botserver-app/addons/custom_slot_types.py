import logging
import math

from rasa.shared.core.slots import Slot


logger = logging.getLogger(__name__)

class BaseInfoStatus(Slot):
    status_num = 2
    bit_per_status = 2

    def type_name(self):
        raise NotImplementedError('type_name must be defined.')

    def feature_dimensionality(self):
        return self.status_num * self.bit_per_status

    def _as_feature(self):
        value = self.value
        status_num = self.status_num
        dim_size = self.feature_dimensionality()

        r = [0.0] * dim_size

        if value is None or len(value) == 0:
            return r

        assert isinstance(value, list), "_as_feature: expect value to be an instance of list, actual type: %s" % (type(value))

        if len(value) > status_num:
            logging.warning('[WARNING, FATAL] Slot value is incorrectly represented, %s > %s (len(value) > status_num), value: %s', len(value), status_num, str(value))

        idx = 0
        for status in value:
            if status:
                r[idx] = 1.0
                r[idx + 1] = 0.0
            else:
                r[idx] = 0.0
                r[idx + 1] = 1.0

            idx += 2

            if idx >= dim_size:
                break

        return r


class BkinfoStatus(BaseInfoStatus):
    status_num = 5
    bit_per_status = 2

    def type_name(self):
        return 'addons.custom_slot_types.BkinfoStatus'


class ProfileInfoStatus(BaseInfoStatus):
    status_num = 8
    bit_per_status = 2

    def type_name(self):
        return 'addons.custom_slot_types.ProfileInfoStatus'


if __name__ == '__main__':

    # assert Exception raised
    # uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    # uit.value = 'notalist'
    # uit._as_feature()

    # assert warning
    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    print('assert warning messae')
    uit.value = [None, 'test', None, None, None, None]
    uit._as_feature()

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = None
    actual = uit._as_feature()
    expected = [0.0, 0.0] * 5
    assert actual == expected, str(actual)


    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = [None, None, None, None, None]
    actual = uit._as_feature()
    expected = [0.0, 1.0] * 5
    assert actual == expected, str(actual)

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = ['test', 'test', 'test', 'test', 'test']
    actual = uit._as_feature()
    expected = [1.0, 0.0] * 5
    assert actual == expected, str(actual)

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = ['test', None, None, None, 'test']
    actual = uit._as_feature()
    expected = [1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    assert actual == expected, str(actual)

    print('Finished.')
