import logging

from rasa.shared.core.slots import Slot


logger = logging.getLogger(__name__)

class BkinfoStatus(Slot):
    status_num = 5

    def type_name(self):
        return 'addons.custom_slot_types.BkinfoStatus'

    def feature_dimensionality(self):
        return 2 * self.status_num

    def _as_feature(self):
        value = self.value
        status_num = self.status_num
        dim_size = self.feature_dimensionality()

        r = [0, 1.0] * status_num

        assert isinstance(value, list), "BkinfoStatus value must be an instance of list"

        if len(value) > self.status_num:
            logging.warning('[WARNING, FATAL] Slot value is incorrectly represented, %s > %s (len(value) > status_num), value: %s', len(value), status_num, str(value))

        idx = 0
        for status in value:
            if status:
                r[idx] = 1.0
                r[idx + 1] = 0
            else:
                r[idx] = 0
                r[idx + 1] = 1.0

            idx += 2

            if idx >= dim_size:
                break

        return r


if __name__ == '__main__':

    # assert Exception raised
    # uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    # uit.value = 'notalist'
    # uit._as_feature()

    # assert warning
    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = [None, 'test', None, None, None, 'test']
    uit._as_feature()

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = []
    actual = uit._as_feature()
    expected = [0, 1.0] * 5
    assert actual == expected, str(actual)


    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = [None, None, None, None, None]
    actual = uit._as_feature()
    expected = [0, 1.0] * 5
    assert actual == expected, str(actual)

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = ['test', 'test', 'test', 'test', 'test']
    actual = uit._as_feature()
    expected = [1.0, 0] * 5
    assert actual == expected, str(actual)

    uit = BkinfoStatus(name='test_slot', mappings=[{'type': 'custom'}])
    uit.value = ['test', None, None, None, 'test']
    actual = uit._as_feature()
    expected = [1.0, 0] + [0, 1.0] + [0, 1.0] + [0, 1.0] + [1.0, 0]
    assert actual == expected, str(actual)

    print('Passed.')


