/* SPDX-License-Identifier: AGPL-3.0-only */
import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap-vue/dist/bootstrap-vue.css';
import 'highlightjs/styles/solarized-dark.css';
import 'vue-multiselect/dist/vue-multiselect.min.css';
import '@/style.less';

import Vue from 'vue';
import BootstrapVue from 'bootstrap-vue';
import axios from 'axios';
import Toasted from 'vue-toasted';
import localforage from 'localforage';
import memoryStorageDriver from 'localforage-memoryStorageDriver';
import VueMasonry from 'vue-masonry-css';
import moment from 'moment';

import '@/polyfills';
import App from '@/App';
import router, { setRestoreRoute } from '@/router';
import { htmlEscape } from '@/utils';
import store from './store';
import * as mutationTypes from './store/mutation-types';

Vue.use(BootstrapVue);
Vue.use(Toasted);
Vue.use(VueMasonry);

Vue.config.productionTip = false;

axios.defaults.transformRequest.push((data, headers) => {
    if (store.state.user.jwtToken) {
        headers.Authorization = `Bearer ${store.state.user.jwtToken}`;
    }
    return data;
});

// Fix axios automatically parsing all responses as JSON... WTF!!!
axios.defaults.transformResponse = [
    function defaultTransformResponse(data, headers) {
        switch (headers['content-type']) {
            case 'application/json':
                return JSON.parse(data);
            default:
                return data;
        }
    },
];

axios.interceptors.response.use(
    response => response,
    (() => {
        let toastVisible = false;
        return error => {
            const { config, response, request } = error;

            if (!toastVisible && !response && request) {
                toastVisible = true;
                Vue.toasted.error(
                    'There was an error connecting to the server... Please try again later',
                    {
                        position: 'bottom-center',
                        closeOnSwipe: false,
                        duration: 3000,
                        onComplete: () => {
                            toastVisible = false;
                        },
                    },
                );
            } else if (
                config.method === 'get' &&
                response.status === 401 &&
                !config.url.match(/\/api\/v1\/login.*/)
            ) {
                if (router.currentRoute.name !== 'login') {
                    setRestoreRoute(router.currentRoute);
                    store.dispatch('user/logout').then(() => {
                        router.push({ name: 'login' });
                    });
                }
                if (!toastVisible) {
                    toastVisible = true;
                    Vue.toasted.error(
                        'You are currently not logged in. Please log in to view this page.',
                        {
                            position: 'bottom-center',
                            closeOnSwipe: false,
                            action: {
                                text: '✖',
                                onClick(_, toastObject) {
                                    toastObject.goAway(0);
                                    toastVisible = false;
                                },
                            },
                        },
                    );
                }
            }

            throw error;
        };
    })(),
);

Vue.prototype.$http = axios;

const DRIVERS = [
    localforage.INDEXEDDB,
    localforage.WEBSQL,
    localforage.LOCALSTORAGE,
    'memoryStorageDriver',
];

let inLTI = false;
Vue.util.defineReactive(
    Vue.prototype,
    '$inLTI',
    inLTI,
    val => {
        if (val === true) {
            inLTI = val;
        } else {
            throw new TypeError('You can only set $inLTI to true');
        }
    },
    true,
);

let ltiProvider = null;
Vue.util.defineReactive(
    Vue.prototype,
    '$ltiProvider',
    ltiProvider,
    val => {
        if (ltiProvider === null) {
            ltiProvider = val;
        } else {
            throw new TypeError('You can only set $ltiProvider once');
        }
    },
    true,
);

let LTIAssignmentId = null;
Vue.util.defineReactive(
    Vue.prototype,
    '$LTIAssignmentId',
    LTIAssignmentId,
    val => {
        if (val == null) {
            throw new TypeError('You cannot set this to null or undefined');
        }
        if (LTIAssignmentId == null || val === LTIAssignmentId) {
            LTIAssignmentId = val;
        } else {
            throw new TypeError('You cannot change this property once it is set');
        }
    },
    true,
);

Vue.prototype.$userConfig = UserConfig;

// eslint-disable-next-line
localforage.defineDriver(memoryStorageDriver).then(() => {
    Vue.prototype.$hlanguageStore = localforage.createInstance({
        name: 'highlightLanguageStore',
        driver: DRIVERS,
    });
    Vue.prototype.$whitespaceStore = localforage.createInstance({
        name: 'showWhitespaceStore',
        driver: DRIVERS,
    });

    Vue.prototype.$htmlEscape = htmlEscape;

    Vue.prototype.$hasPermission = (permission, courseId, asMap) => {
        function makeResponse(map) {
            if (typeof permission === 'string') {
                return map[permission];
            } else if (asMap) {
                return map;
            } else {
                return permission.map(p => map[p]);
            }
        }
        if (courseId) {
            return store.dispatch('courses/loadCourses').then(() => {
                const map = store.getters['courses/courses'][courseId].permissions;
                return makeResponse(map);
            });
        } else {
            return Promise.resolve(makeResponse(store.getters['user/permissions']));
        }
    };

    /* eslint-disable no-new */
    const app = new Vue({
        el: '#app',
        router,
        template: '<App/>',
        components: { App },
        store,

        data() {
            return {
                screenWidth: window.innerWidth,
                smallWidth: 628,
                mediumWidth: 768,
                largeWidth: 992,
                now: moment(),
            };
        },

        created() {
            window.addEventListener('resize', () => {
                this.screenWidth = window.innerWidth;
            });

            setTimeout(() => {
                this.now = moment();
            }, 60000);
        },

        computed: {
            $isSmallWindow() {
                return this.screenWidth <= this.smallWidth;
            },

            $isMediumWindow() {
                return this.screenWidth >= this.mediumWidth;
            },

            $isLargeWindow() {
                return this.screenWidth >= this.largeWidth;
            },

            isEdge() {
                return window.navigator.userAgent.indexOf('Edge') > -1;
            },

            isSafari() {
                const ua = window.navigator.userAgent;
                // Contains safari and does not contain Chrome as Google Chrome
                // contains Safari and Chrome.
                return ua.indexOf('Safari') > -1 && ua.indexOf('Chrome') < 0;
            },

            // Detect if browser is Internet Explorer,
            // source: https://s.codepen.io/boomerang/iFrameKey-82faba85-1442-af7e-7e36-bd4e4cc10796/index.html
            isIE() {
                const ua = window.navigator.userAgent;

                // Test values; Uncomment to check result …

                // IE 10
                // ua = 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)';

                // IE 11
                // ua = 'Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko';

                return ua.indexOf('MSIE ') > -1 || ua.indexOf('Trident/') > -1;
            },

            $now() {
                return this.now;
            },
        },
    });

    // Clear some items in vuex store on CTRL-F5
    document.addEventListener(
        'keydown',
        async event => {
            let isF5;
            if (event.key !== undefined) {
                isF5 = event.key === 'F5';
            } else if (event.keyIdentifier !== undefined) {
                isF5 = event.keyIdentifier === 'F5';
            } else if (event.keyCode !== undefined) {
                isF5 = event.keyCode === 116;
            }

            if (isF5 && (event.ctrlKey || event.shiftKey)) {
                event.preventDefault();
                await app.$store.commit(`user/${mutationTypes.CLEAR_CACHE}`);
                window.location.reload(true);
            }
        },
        true,
    );
});
