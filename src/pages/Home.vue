<template>
<div class="page home">
    <div class="login-wrapper" v-if="!loggedIn">
        <img class="logo" src="static/img/codegrade.svg" v-if="this.$store.getters['pref/darkMode']"/>
        <img class="logo" src="static/img/codegrade-inv.svg" v-else/>
        <login class="login"/>
    </div>
    <home-grid v-else/>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import { Login, HomeGrid } from '@/components';

import { setPageTitle } from './title';

export default {
    name: 'home-page',

    computed: {
        ...mapGetters('user', [
            'loggedIn',
        ]),
    },

    mounted() {
        setPageTitle();
    },


    components: {
        Login,
        HomeGrid,
    },
};
</script>

<style lang="less" scoped>
@import "~mixins.less";

.page.home .login-wrapper {
    margin: 2em auto;
    .login {
        @media @media-medium {
            max-width: 768px;
            margin: 0 auto;
        }
    }
}

.logo {
    display: block;
    margin-left: auto;
    margin-right: auto;
    width: 50%;
    margin-bottom: 1em;
}
</style>
