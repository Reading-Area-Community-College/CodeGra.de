<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<flat-pickr
    class="form-control datetime-picker"
    :value="value"
    :config="internalConfig"/>
</template>

<script>
import flatPickr from 'vue-flatpickr-component';
import confirmDatePlugin from 'flatpickr/dist/plugins/confirmDate/confirmDate';

export default {
    name: 'datetime-picker',
    props: {
        value: {},
        config: {
            type: Object,
            default: () => ({}),
        },
    },

    computed: {
        internalConfig() {
            return Object.assign(
                {},
                {
                    enableTime: true,
                    plugins: [
                        confirmDatePlugin({
                            showAlways: true,
                            confirmIcon: '',
                            confirmText: 'Close',
                        }),
                    ],
                    minuteIncrement: 1,
                    time_24hr: true,
                    onChange: this.emitDate,
                    onClose: this.emitDate,
                    defaultHour: 23,
                    defaultMinute: 59,
                },
                this.config,
            );
        },
    },

    methods: {
        emitDate(selectedDates) {
            if (!selectedDates.length) {
                return;
            }

            if (this.internalConfig.mode === 'multiple') {
                this.$emit('input', selectedDates.map(el => el.toISOString()));
            } else {
                this.$emit('input', selectedDates[0].toISOString());
            }
        },
    },

    components: {
        flatPickr,
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.datetime-picker {
    &.flatpickr-input:not(:disabled) {
        background-color: white;
    }
    &:disabled {
        cursor: not-allowed;
    }

    &.flatpickr-input {
        .default-form-control-colors;
    }
}
</style>

<style src="flatpickr/dist/flatpickr.css"/>

<style src="flatpickr/dist/plugins/confirmDate/confirmDate.css"/>
