<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="submit-input"
     @keyup.ctrl.enter="$refs.submitButton.onClick">
    <b-form-fieldset>
        <b-input-group>
            <input type="text"
                    class="form-control"
                    :disabled="disabled"
                    :placeholder="placeholder"
                    v-model="name"/>
            <b-button-group>
                <submit-button ref="submitButton"
                                label="Add"
                                :submit="submit"
                                @after-success="afterSubmit"/>
            </b-button-group>
        </b-input-group>
    </b-form-fieldset>
</div>
</template>

<script>
import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'submit-input',

    props: {
        placeholder: {
            default: undefined,
        },
    },

    data() {
        return {
            name: '',
            disabled: false,
        };
    },
    components: {
        SubmitButton,
        Loader,
    },

    methods: {
        submit() {
            if (this.name === '' || this.name == null) {
                throw new Error('Please give a name');
            }

            this.disabled = true;

            return new Promise((resolve, reject) => {
                this.$emit('create', this.name, resolve, reject);
            });
        },

        afterSubmit() {
            this.name = '';
            this.disabled = false;
        },
    },
};
</script>

<style lang="less">
.submit-input .btn {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    height: 100%;
}
</style>
