<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
    <b-alert variant="danger" show v-if="error" class="box">
        <p style="text-align: center; font-size: 1.3em;">
            Something went wrong during the LTI launch!
            <br>
            <span v-if="errorMsg">{{ errorMsg }}</span>
            <span v-else>Please try again.</span>
        </p>
    </b-alert>
    <loader v-else/>
</template>

<script>
import 'vue-awesome/icons/times';
import { Loader } from '@/components';
import { mapActions } from 'vuex';

import { setPageTitle } from './title';

export default {
    name: 'lti-launch-page',

    data() {
        return {
            error: false,
            errorMsg: false,
        };
    },

    mounted() {
        this.secondStep(true);
    },

    methods: {
        ...mapActions('user', ['logout', 'updateAccessToken']),
        ...mapActions('plagiarism', { clearPlagiarismCases: 'clear' }),

        secondStep(first) {
            this.$inLTI = true;

            setPageTitle('LTI is launching, please wait');

            this.$http
                .post('/api/v1/lti/launch/2', {
                    jwt_token: this.$route.query.jwt,
                })
                .then(async ({ data }) => {
                    if (data.access_token) {
                        await this.updateAccessToken(data.access_token);
                    } else {
                        this.clearPlagiarismCases();
                    }

                    this.$LTIAssignmentId = data.assignment.id;
                    if (data.new_role_created) {
                        this.$toasted.info(
                            `You do not have any permissions yet, please ask your teacher to enable them for your role "${
                                data.new_role_created
                            }".`,
                            {
                                position: 'bottom-center',
                                closeOnSwipe: false,
                                action: {
                                    text: '✖',
                                    onClick: (e, toastObject) => {
                                        toastObject.goAway(0);
                                    },
                                },
                            },
                        );
                    }
                    if (data.updated_email) {
                        this.$toasted.info(
                            `Your email was updated to "${
                                data.updated_email
                            }" which is the email registered with your LMS.`,
                            {
                                position: 'bottom-center',
                                closeOnSwipe: false,
                                action: {
                                    text: '✖',
                                    onClick: (e, toastObject) => {
                                        toastObject.goAway(0);
                                    },
                                },
                            },
                        );
                    }
                    if (this.$route.query.redirect && this.$route.query.redirect.startsWith('/')) {
                        this.$router.replace(this.$route.query.redirect);
                    } else {
                        this.$router.replace({
                            name: 'assignment_submissions',
                            params: {
                                courseId: data.assignment.course.id,
                                assignmentId: data.assignment.id,
                            },
                        });
                    }
                })
                .catch(err => {
                    if (first && err.response && err.response.status === 401) {
                        this.logout()
                            .then(() => {
                                this.secondStep(false);
                            })
                            .catch(() => {
                                this.error = true;
                            });
                    }
                    try {
                        this.errorMsg = err.response.data.message;
                    } finally {
                        this.error = true;
                    }
                });
        },
    },

    components: {
        Loader,
    },
};
</script>

<style>
.box {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>
