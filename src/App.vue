<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div id="app" :class="{ dark: hasDarkMode, lti: $inLTI }">
    <loader v-if="loading" page-loader/>
    <sidebar ref="sidebar"
             v-if="!loading && showSidebar"/>
    <div class="container-fluid" v-if="!loading">
        <main class="row justify-content-center" id="main-content">
            <b-alert class="ie-banner"
                     :show="$root.isIE"
                     variant="warning"
                     dismissible>
                It seems the browser you are using is Internet Explorer which
                is not fully supported. We suggest you use another browser to get
                the most out of CodeGrade!
            </b-alert>
            <router-view class="page col-lg-12"/>
            <footer-bar v-if="showFooter"/>
        </main>
    </div>
    <div v-if="showFrameBorder" class="frame-border"/>
</div>
</template>

<script>
import { mapActions } from 'vuex';

import { setRestoreRoute } from '@/router';
import { Loader, FooterBar, Sidebar } from '@/components';
import { NO_LOGIN_ALLOWED_ROUTES, NO_LOGIN_REQUIRED_ROUTES } from '@/constants';

export default {
    name: 'app',

    computed: {
        hasDarkMode() {
            return this.$store.getters['pref/darkMode'];
        },

        showSidebar() {
            return this.$route.name !== 'lti-launch';
        },

        showFooter() {
            return (
                this.$route.name !== 'submission' &&
                this.$route.name !== 'submission_file' &&
                this.$route.name !== 'plagiarism_detail'
            );
        },

        showFrameBorder() {
            return window !== window.top && this.$ltiProvider && this.$ltiProvider.addBorder;
        },
    },

    data() {
        return {
            loading: true,
        };
    },

    methods: {
        ...mapActions('user', ['verifyLogin']),
    },

    created() {
        if (this.$route.query.inLTI !== undefined) {
            this.$inLTI = true;
        }

        let popoversShown = false;

        document.body.addEventListener(
            'click',
            event => {
                popoversShown = false;
                if (!event.target.closest('.popover-body')) {
                    if (!event.target.closest('.sidebar') && this.$refs.sidebar) {
                        this.$refs.sidebar.$emit('sidebar::close');
                    }

                    setTimeout(() => {
                        this.$nextTick(() => {
                            if (!popoversShown) {
                                this.$root.$emit('bv::hide::popover');
                            }
                        });
                    }, 10);
                }
            },
            true,
        );

        this.$root.$on('bv::popover::show', () => {
            popoversShown = true;
        });

        document.body.addEventListener(
            'keyup',
            event => {
                if (event.key === 'Escape') {
                    this.$root.$emit('bv::hide::popover');
                }
            },
            true,
        );
    },

    async mounted() {
        await this.verifyLogin()
            .then(
                () => {
                    const route = this.$route.name;

                    if (NO_LOGIN_ALLOWED_ROUTES.has(route)) {
                        this.$router.push({ name: 'home' });
                    }
                },
                () => {
                    const route = this.$route.name;

                    if (!route || !NO_LOGIN_REQUIRED_ROUTES.has(route)) {
                        setRestoreRoute(this.$route);
                        this.$router.push({ name: 'login' });
                    }
                },
            )
            .then(() => {
                this.loading = false;
            });
    },

    components: {
        Loader,
        FooterBar,
        Sidebar,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

#app {
    display: flex;
    flex-direction: row;
    min-height: 100vh;
}

.container-fluid {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    width: auto;
    min-width: 0;

    main {
        position: relative;
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;

        .default-background;
        .default-color;
    }

    .page {
        flex: 1 1 auto;
        margin-bottom: 1rem;
    }
}

.ie-banner {
    position: absolute;
    top: 1rem;
    left: 1rem;
    right: 1rem;
    z-index: 100;
}

.frame-border {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
    border: 1px solid @color-border-gray-lighter;
    z-index: 1000;
    #app.dark & {
        display: none;
    }
}
</style>
