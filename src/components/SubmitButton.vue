<template>
<b-button :disabled="pending || disabled"
          class="submit-button"
          :id="btnId"
          :variant="variants[state]"
          :size="size"
          :tabindex="tabindex"
          style="height: 100%;"
          @click="onClick">
    <loader :scale="1" center v-if="pending"/>
    <span v-else-if="label">{{ label }}</span>
    <slot v-else/>

    <b-popover :show="shouldShowMessage"
               triggers=""
               :target="btnId"
               :placement="popoverPlacement">
        <span>{{ err }}</span>
    </b-popover>

    <b-popover v-if="confirm"
               :show="showConfirm"
               @hide="resetConfirm"
               triggers=""
               :target="btnId"
               :placement="popoverPlacement"
               ref="confirmPopover">
        <p>{{ confirm }}</p>

        <b-button-toolbar justify>
            <b-button variant="danger"
                      size="sm"
                      @click="onClick">
                Yes
            </b-button>
            <b-button variant="success"
                      size="sm"
                      @click="resetConfirm">
                No
            </b-button>
        </b-button-toolbar>
    </b-popover>
</b-button>
</template>

<script>
import Loader from './Loader';

let i = 0;

export const SubmitButtonCancelled = Object.create(Error);

export default {
    name: 'submit-button',

    data() {
        return {
            pop: true,
            err: '',
            pending: false,
            state: 'default',
            cancelled: true,
            btnId: this.id || `submitButton-i-${i++}`,
            variants: {
                default: this.default,
                success: this.success,
                failure: this.failure,
                warning: this.warning,
            },
            mult: 1,
            timeout: null,
            showConfirm: false,
            confirmEvent: null,
        };
    },

    computed: {
        shouldShowMessage() {
            return (this.showError &&
                    (this.state === 'failure' || this.state === 'warning') &&
                    (Boolean(this.err) || this.showEmpty));
        },
    },

    props: {
        id: {
            type: String,
            default: null,
        },
        tabindex: {
            default: '0',
        },

        popoverPlacement: {
            type: String,
            default: 'top',
        },
        disabled: {
            type: Boolean,
            default: false,
        },
        label: {
            type: [String, Boolean],
            default: 'Submit',
        },
        size: {
            type: String,
            default: 'md',
        },
        delay: {
            type: Number,
            default: 1000,
        },
        default: {
            type: String,
            default: 'primary',
        },
        success: {
            type: String,
            default: 'success',
        },
        failure: {
            type: String,
            default: 'danger',
        },
        warning: {
            type: String,
            default: 'warning',
        },
        showEmpty: {
            type: Boolean,
            default: true,
        },
        showError: {
            type: Boolean,
            default: true,
        },
        confirm: {
            type: String,
            default: '',
        },
    },

    methods: {
        submit(promise) {
            this.pending = true;
            this.cancelled = false;
            return Promise.resolve(promise).then(
                res => !this.cancelled && this.succeed(res),
                (err) => {
                    if (this.cancelled) {
                        throw SubmitButtonCancelled;
                    } else {
                        return this.fail(err);
                    }
                },
            );
        },

        reset() {
            this.cancelled = true;
            if (this.timeout != null) {
                clearTimeout(this.timeout);
                this.timeout = null;
            }

            this.state = 'default';
            this.err = '';
            this.pending = false;
        },

        succeed(res) {
            this.pending = false;
            return this.update('success')
                .then(() => res);
        },

        cancel() {
            this.cancelled = true;
        },

        warn(err) {
            this.pending = false;
            this.err = err;
            return this.update('warning', 3);
        },

        fail(err) {
            this.pending = false;
            this.err = err;
            return this.update('failure', 3)
                .then(() => { throw err; });
        },

        update(state, mult = 1) {
            this.state = state;
            return new Promise((resolve) => {
                if (this.timeout != null) {
                    clearTimeout(this.timeout);
                }
                if (this.mult * mult === 0) {
                    resolve();
                    return;
                }
                this.timeout = setTimeout(() => {
                    this.reset();
                    resolve();
                }, this.delay * mult * this.mult);
            });
        },

        onClick(event) {
            if (this.confirm && !this.showConfirm) {
                this.$refs.confirmPopover.$emit('open');
                this.showConfirm = true;
                this.confirmEvent = event;
            } else {
                this.$emit('click', this.confirmEvent || event);
                this.resetConfirm();
            }
        },

        resetConfirm() {
            this.showConfirm = false;
            this.confirmEvent = null;
        },
    },

    components: {
        Loader,
    },
};
</script>

<style lang="less" scoped>
.btn-toolbar {
    width: 60%;
    margin: 0 auto;
}

.btn .fa-icon {
    margin-right: 0 !important;
}

.loader {
    padding: 0.25em 0;
}
</style>


<docs>
Submit button component to be used when
an action involves submitting
data to the server.

Props:

label
    Text in the button. The label must explicitly be set to an empty
    string in order to use the button's inner html. Default: 'Submit'.
size
    Bootstrap size such as 'sm' or 'md'. Default: bootstrap-vue default.
delay
    Number of milliseconds the button will stay in its success/failure
    state before going back to the default state. Default: 1000.
default
    Default bootstrap button variant for the button. Default: 'primary'.
success
    Bootstrap button variant to be used when the promise resolved.
    Default: 'success'.
failure
    Bootstrap button variant to be used when the promise rejected.
    Default: 'danger'.

Methods:

submit(promise)
    Disable the button and show a spinning loader icon until `promise`
    resolves. Then put the button in the success state if the promise
    resolved or the failure state if the promise rejected, for `delay`
    milliseconds.
    Returns a promise that resolves (rejects) when the button goes
    from its success/failure state back to the default state and that
    has the same resolution as the promise passed in.

succeed()
    Put the button in the success state for `delay` milliseconds.
    Returns a promise that resolves when the button goes from the
    success/failure state back to the default state.

fail()
    Put the button in the failure state for `delay` milliseconds.
    Returns a promise that rejects when the button goes from the
    success/failure state back to the default state.

Example:

    <template>
        <submit-button
            ref="submitButton"
            @click="doSubmit"
        />
    </template>

    <script>
    /* eslint-disable */
    export const MyComp = {
        methods: {
            doSubmit() {
                this.$refs.submitButton.submit(
                    this.$http.post(route, data),
                ).then((res) => {
                    // handle response
                }, (err) => {
                    // handle error
                });
            },
        },
    };
    </script>
</docs>
