<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="login">
    <b-form-fieldset>
        <input type="text"
               class="form-control"
               placeholder="Username"
               v-model="username"
               ref="username"
               @keyup.enter="$refs.submit.onClick"/>
    </b-form-fieldset>

    <b-form-fieldset>
        <password-input v-model="password"
                        placeholder="Password"
                        @keyup.native.enter="$refs.submit.onClick"/>
    </b-form-fieldset>

    <div class="text-center">
        <submit-button label="Login"
                       ref="submit"
                       :submit="submit"
                       @success="success"
                       :wait-at-least="0">
            <template slot="warning" slot-scope="warning">
                {{ warning.warning }}<br>
                Close this message to continue.
            </template>
        </submit-button>

        <div class="login-links">
            <router-link :to="{ name: 'forgot' }">
                Forgot password
            </router-link>
        </div>
    </div>
</div>
</template>

<script>
import { mapActions } from 'vuex';

import PasswordInput from './PasswordInput';
import SubmitButton from './SubmitButton';

export default {
    name: 'login',

    data() {
        return {
            username: '',
            password: '',
        };
    },

    components: {
        PasswordInput,
        SubmitButton,
    },

    mounted() {
        this.$nextTick(() => {
            if (this.$refs.username) {
                this.$refs.username.focus();
            }
        });
    },

    methods: {
        ...mapActions('user', ['login']),

        submit() {
            if (!this.password || !this.username) {
                return Promise.reject(new Error('Please enter a username and password.'));
            }

            return this.$http.post('/api/v1/login?with_permissions', {
                username: this.username,
                password: this.password,
            });
        },

        success(response) {
            this.login(response).then(() => {
                this.$router.replace({ name: 'home' });
                this.$emit('login');
            });
        },
    },
};
</script>

<style lang="less" scoped>
@link-margin: 2em;
.login-links {
    margin-top: 1rem;

    a {
        text-decoration: underline !important;
    }
}
</style>
