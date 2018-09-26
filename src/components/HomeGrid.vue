<template>
<div class="home-grid">
    <local-header>
        <template slot="title">
            Welcome {{ nameOfUser }}!
        </template>
        <img class="large" src="/static/img/codegrade.svg" v-if="darkMode"/>
        <img class="large" src="/static/img/codegrade-inv.svg" v-else/>
        <img class="small" src="/static/img/logo.svg" v-if="darkMode"/>
        <img class="small" src="/static/img/logo-inv.svg" v-else/>
    </local-header>
    <loader v-if="loadingCourses"/>
    <div v-else-if="courses.length === 0">
        <span class="no-courses">You have no courses yet!</span>
    </div>
    <masonry :cols="{default: 3, [$root.largeWidth]: 2, [$root.mediumWidth]: 1 }"
             :gutter="30"
             class="outer-block"
             v-else>
        <div class="card-wrapper" v-for="course in courses" :key="course.id">
            <b-card no-body>
                <b-card-header :class="`text-${getColorPair(course.name).color}`"
                               :style="{ backgroundColor: getColorPair(course.name).background }">
                    <div style="display: flex">
                        <b class="course-name">{{ course.name }}</b>
                        <router-link v-if="course.canManage"
                                     :to="manageCourseRoute(course)"
                                     v-b-popover.bottom.hover="'Manage course'"
                                     class="course-manage">
                            <icon name="gear"/>
                        </router-link>
                    </div>
                </b-card-header>
                <b-card-body class="card-no-padding">
                    <div class="card-text">
                        <table class="table table-hover assig-list"
                               v-if="course.assignments.length > 0">
                            <tbody>
                                <router-link v-for="assig in course.assignments"
                                             :key="assig.id"
                                             :to="submissionsRoute(assig)"
                                             class="assig-list-item">
                                    <td>
                                        {{ assig.name }}<br>

                                        <small>
                                            Due {{ moment(assig.deadline).from(now) }}
                                        </small>
                                    </td>
                                    <td>
                                        <assignment-state :assignment="assig"
                                                        :editable="false"
                                                        size="sm"/>
                                    </td>
                                    <td v-if="assig.canManage">
                                        <router-link :to="manageAssignmentRoute(assig)"
                                                     v-b-popover.bottom.hover="'Manage assignment'">
                                            <icon name="gear" class="gear-icon"/>
                                        </router-link>
                                    </td>
                                </router-link>
                            </tbody>
                        </table>

                        <p class="no-assignments" v-else>
                            No assignments for this course.
                        </p>
                    </div>
                </b-card-body>
            </b-card>
        </div>
    </masonry>
</div>
</template>


<script>
import moment from 'moment';
import { mapGetters, mapActions } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';

import { hashString, cmpNoCase } from '@/utils';

import AssignmentState from './AssignmentState';
import UserInfo from './UserInfo';
import Loader from './Loader';
import LocalHeader from './LocalHeader';

const COLOR_PAIRS = [
    { background: '#70A3A2', color: 'dark' },
    { background: '#DFD3AA', color: 'dark' },
    { background: '#DFB879', color: 'dark' },
    { background: '#956F48', color: 'light' },
    { background: '#4F5F56', color: 'light' },
    { background: '#A7AE91', color: 'dark' },
    { background: '#D7CEA6', color: 'dark' },
    { background: '#CC3A28', color: 'light' },
    { background: '#598D86', color: 'dark' },
    { background: '#E6DCCD', color: 'dark' },
    { background: '#D6CE5B', color: 'dark' },
    { background: '#D97E71', color: 'dark' },
    { background: '#5D8D7D', color: 'dark' },
    { background: '#D2CF9F', color: 'dark' },
    { background: '#EADB93', color: 'dark' },
    { background: '#CB5452', color: 'light' },
    { background: '#65686C', color: 'light' },
    { background: '#B4AEA4', color: 'dark' },
    { background: '#E7EEE9', color: 'dark' },
    { background: '#EAB66C', color: 'dark' },
];

export default {
    name: 'home-grid',

    data() {
        return {
            loadingCourses: true,
            moment,
            now: moment(),
            nowInterval: null,
        };
    },

    computed: {
        ...mapGetters('courses', { unsortedCourses: 'courses' }),
        ...mapGetters('user', { nameOfUser: 'name' }),
        ...mapGetters('pref', ['darkMode']),

        courses() {
            return Object.values(this.unsortedCourses).sort(
                (a, b) => cmpNoCase(a.name, b.name),
            );
        },
    },

    mounted() {
        this.loadCourses().then(() => {
            this.loadingCourses = false;
        });

        this.nowInterval = setInterval(() => {
            this.now = moment();
        }, 60000);
    },

    destroyed() {
        if (this.nowInterval) {
            clearInterval(this.nowInterval);
        }
    },

    methods: {
        ...mapActions('courses', ['loadCourses']),

        getColorPair(name) {
            const hash = hashString(name);
            return COLOR_PAIRS[hash % COLOR_PAIRS.length];
        },

        manageCourseRoute(course) {
            return {
                name: 'manage_course',
                params: {
                    courseId: course.id,
                },
            };
        },

        manageAssignmentRoute(assignment) {
            return {
                name: 'manage_assignment',
                params: {
                    courseId: assignment.course.id,
                    assignmentId: assignment.id,
                },
            };
        },

        submissionsRoute(assignment) {
            return {
                name: 'assignment_submissions',
                params: {
                    courseId: assignment.course.id,
                    assignmentId: assignment.id,
                },
            };
        },
    },

    components: {
        AssignmentState,
        Icon,
        UserInfo,
        Loader,
        LocalHeader,
    },
};
</script>

<style lang="less" scoped>
@import "~mixins.less";

.local-header img {
    float: right;

    &.large {
        height: 1.3em;
        margin-top: .5rem;
    }

    &.small {
        height: 1.8em;
    }

    @media @media-small {
        &.large {
            display: none;
        }
    }

    @media @media-no-small {
        &.small {
            display: none;
        }
    }
}

.home-grid .outer-block {
    .card-body.card-no-padding {
        padding: 0;
    }

    .assig-list {
        margin-bottom: 0;

        .assig-list-item {
            display: table-row;

            &:nth-of-type(even) {
                background-color: rgba(0, 0, 0, .05);
            }

            &:hover {
                background-color: rgba(0, 0, 0, .075);
            }
        }

        td:not(:first-child) {
            width: 1px;
            white-space: nowrap;
        }

        td:last-child a {
            padding-bottom: 0;
        }

        a:hover {
            text-decoration: none;

            .fa-icon {
                border-bottom: none;
            }
        }

        .fa-icon {
            margin-top: 5px;
        }
    }

    .card-wrapper {
        padding-bottom: 1em;

        .card-body {
            @media @media-medium {
                max-height: 15em;
                overflow: auto;
            }
        }

        .card-header {
            padding: .75rem;

            .course-name {
                display: flex;
                flex: 1 1 auto;
            }

            .course-manage {
                display: flex;
                flex: 0 0 auto;
            }

            .fa-icon {
                display: block;
                margin: auto;
            }
        }

        .card-header.text-dark {
            color: @text-color !important;

            .fa-icon {
                fill: @text-color;
            }
        }

        .card-header.text-light {
            color: @text-color-dark !important;

            .fa-icon {
                fill: @text-color-dark;
            }
        }
    }
}

a {
    #app.dark & {
        color: @text-color-dark;

        &:hover {
            color: darken(@text-color-dark, 10%);
        }
    }

    .gear-icon {
        border-bottom: 1px solid transparent;
    }

    &:hover .gear-icon {
        border-bottom: 1px solid lighten(@color-primary, 10%);

        #app.dark & {
            border-color: darken(@text-color-dark, 10%);
        }
    }
}

.no-courses {
    display: block;
    font-size: 1.5rem;
    text-align: center;
    color: @color-secondary-text;

    #app.dark & {
        color: @color-light-gray;
    }
}

.no-assignments {
    margin: 1rem .75rem;
    color: @color-secondary-text;

    #app.dark & {
        color: @color-light-gray;
    }
}
</style>
