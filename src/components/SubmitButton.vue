<template>
<b-button :id="btnId"
          class="submit-button"
          :class="`state-${state}`"
          :tabindex="tabindex"
          :disabled="isDisabled"
          :variant="currentVariant"
          :size="size"
          @click="onClick">

    <span class="label success">
        <slot name="success-label">
            <icon name="check" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label warning">
        <slot name="warning-label">
            <icon name="warning" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label error">
        <slot name="error-label">
            <icon name="times" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label pending">
        <slot name="pending-label">
            <loader :scale="iconScale"/>
        </slot>
    </span>
    <span class="label default">
        <slot>
            {{ label }}
        </slot>
    </span>

    <b-popover :placement="popoverPlacement"
               :show="!!error"
               :target="btnId"
               triggers=""
               @hide="onHideError">
        <icon name="times"
              class="hide-button"
              @click.native="hideError"/>

        <span v-if="error">
            <slot name="error" :error="error">
                {{ stringifiedError }}
            </slot>
        </span>
    </b-popover>

    <b-popover :placement="popoverPlacement"
               :show="!!warning"
               :target="btnId"
               triggers=""
               @hide="onHideWarning">
        <icon name="times"
              class="hide-button"
              @click.native="hideWarning"/>

        <span v-if="warning">
            <slot name="warning" :warning="warning">
                {{ warning }}
            </slot>
        </span>
    </b-popover>

    <b-popover v-if="confirm.length > 0"
               :placement="popoverPlacement"
               :show="confirmVisible"
               :target="btnId"
               triggers=""
               @hide="resetConfirm">
        <p class="confirm-message">
            {{ confirm }}
        </p>

        <b-button-toolbar justify>
            <b-button size="sm"
                      variant="outline-primary"
                      class="confirm-button"
                      @click="acceptConfirm">
                Yes
            </b-button>
            <div class="sep"/>
            <b-button size="sm"
                      variant="primary"
                      class="confirm-button"
                      @click="resetConfirm">
                No
            </b-button>
        </b-button-toolbar>
    </b-popover>
</b-button>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/warning';

import { parseWarningHeader, waitAtLeast } from '@/utils';

import Loader from './Loader';

export const SubmitButtonCancelled = Object.create(Error);

let i = 0;

export default {
    name: 'submit-button',

    props: {
        label: {
            type: String,
            default: 'Submit',
        },

        submit: {
            type: Function,
            required: true,
        },

        filterSuccess: {
            type: Function,
            default: x => x,
        },

        filterError: {
            type: Function,
            default: x => {
                throw x;
            },
        },

        id: {
            type: String,
            default: null,
        },

        tabindex: {
            type: [Number, String],
            default: 0,
        },

        disabled: {
            type: Boolean,
            default: false,
        },

        size: {
            type: String,
            default: 'md',
        },

        variant: {
            type: String,
            default: 'primary',
        },

        duration: {
            type: Number,
            default: 750,
        },

        confirm: {
            type: String,
            default: '',
        },

        popoverPlacement: {
            type: String,
            default: 'top',
        },

        waitAtLeast: {
            type: Number,
            default: 250,
        },

        iconScale: {
            type: Number,
            default: 1,
        },
    },

    data() {
        return {
            state: 'default',
            btnId: this.id || `submit-button-${i++}`,
            error: null,
            warning: null,
            response: null,
            confirmVisible: false,
            confirmAccepted: false,
        };
    },

    computed: {
        currentVariant() {
            return {
                default: this.variant,
                pending: this.variant,
                success: 'success',
                error: 'danger',
                warning: 'warning',
            }[this.state];
        },

        stringifiedError() {
            const err = this.error;
            let msg;

            if (err == null) {
                return '';
            } else if (err.response && err.response.data) {
                msg = err.response.data.message;
            } else if (err instanceof Error) {
                msg = err.message;
            } else {
                msg = err.toString();
            }

            return msg || 'Something unknown went wrong';
        },

        isDisabled() {
            return this.disabled || this.state !== 'default' || this.confirmVisible;
        },
    },

    methods: {
        onClick() {
            if (this.isDisabled) {
                return;
            }

            if (this.confirm) {
                this.showConfirm();
            } else {
                this.doSubmit();
            }
        },

        doSubmit() {
            this.state = 'pending';

            waitAtLeast(this.waitAtLeast, Promise.resolve().then(this.submit))
                .then(this.filterSuccess, this.filterError)
                .then(this.onSuccess, this.onError);
        },

        onSuccess(data, fromWarning = false) {
            if (!fromWarning && data && data.headers && data.headers.warning) {
                this.onWarning(data);
                return;
            }

            this.$emit('success', data);

            const done = () => {
                this.$emit('after-success', data);
                this.state = 'default';
            };

            if (this.duration) {
                this.state = 'success';
                setTimeout(done, this.duration);
            } else {
                done();
            }
        },

        onWarning(data) {
            this.$emit('warning', data);
            this.state = 'warning';
            this.warning = parseWarningHeader(data.headers.warning).text;
            this.response = data;
        },

        hideWarning() {
            this.warning = null;
        },

        onHideWarning() {
            this.$emit('after-warning');
            this.state = 'default';
            this.warning = null;

            const res = this.response;
            this.response = null;
            this.onSuccess(res, true);
        },

        onError(err) {
            if (err === SubmitButtonCancelled) {
                this.$emit('cancel', err);
                this.state = 'default';
                return;
            }

            this.$emit('error', err);
            this.state = 'error';
            this.error = err;

            // eslint-disable-next-line
            console.error(err);
        },

        hideError() {
            this.error = null;
        },

        onHideError() {
            this.$emit('after-error');
            this.state = 'default';
            this.error = null;
        },

        showConfirm() {
            this.state = 'pending';
            this.confirmVisible = true;
        },

        resetConfirm() {
            if (!this.confirmAccepted) {
                this.state = 'default';
            }
            this.confirmVisible = false;
            this.confirmAccepted = false;
        },

        acceptConfirm() {
            this.confirmVisible = false;
            this.confirmAccepted = true;
            this.doSubmit();
        },
    },

    components: {
        Icon,
        Loader,
    },
};
</script>

<style lang="less" scoped>
.submit-button {
    position: relative;
}

.label.default {
    opacity: 0;

    .state-default & {
        opacity: 1;
    }
}

.label.success,
.label.warning,
.label.error,
.label.pending {
    display: none;
    position: absolute;
    top: 50%;
    left: 50%;
    line-height: 1;
    transform: translate(-50%, -50%);
    .fa-icon {
        transform: none;
    }
}

.state-success .label.success,
.state-warning .label.warning,
.state-error .label.error,
.state-pending .label.pending,
.state-default .label.default {
    display: initial;
}

.hide-button {
    float: right;
    cursor: pointer;
    opacity: 0.75;
    margin: 0 0 0.25rem 0.5rem;

    &:hover {
        opacity: 1;
    }
}

.confirm-message {
    text-align: justify;
}

.confirm-button {
    flex: 1 1 auto;

    & + .sep {
        width: 0.75rem;
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.submit-button .loader {
    display: inline-block !important;
}

#app.dark ~ .popover .confirm-button:first-child {
    background-color: white;

    &:hover {
        background-color: @color-lighter-gray;
        color: @color-primary;
    }
}
</style>
