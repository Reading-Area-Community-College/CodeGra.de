/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';
import moment from 'moment';

import * as utils from '@/utils';
import * as types from '../mutation-types';
import { MANAGE_ASSIGNMENT_PERMISSIONS, MANAGE_GENERAL_COURSE_PERMISSIONS } from '../../constants';

const getters = {
    courses: state => state.courses,
    assignments: state => {
        if (!state.courses) return {};

        return Object.values(state.courses).reduce((assignments, course) => {
            course.assignments.forEach(assignment => {
                assignments[assignment.id] = assignment;
            });
            return assignments;
        }, {});
    },
};

function getAssignment(state, assignmentId) {
    const assignment = getters.assignments(state)[assignmentId];

    if (assignment == null) {
        throw ReferenceError(`Could not find assignment: ${assignmentId}`);
    }

    return assignment;
}

const actions = {
    async loadCourses({ state, commit, dispatch }) {
        if (state.currentCourseLoader == null) {
            commit(types.SET_COURSES_PROMISE, dispatch('reloadCourses'));
        }

        return state.currentCourseLoader;
    },

    deleteSubmission({ commit }, { assignmentId, submissionId }) {
        commit(types.DELETE_SUBMISSION, { assignmentId, submissionId });
    },

    addSubmission({ commit }, { assignmentId, submission }) {
        submission.formatted_created_at = utils.readableFormatDate(submission.created_at);
        submission.grade = utils.formatGrade(submission.grade);
        commit(types.ADD_SUBMISSION, { assignmentId, submission });
    },

    setRubric({ commit }, { assignmentId, rubric, maxPoints }) {
        commit(types.UPDATE_ASSIGNMENT, {
            assignmentId,
            assignmentProps: { rubric, fixed_max_rubric_points: maxPoints },
        });
    },

    async forceLoadRubric({ commit }, assignmentId) {
        const rubric = await axios
            .get(`/api/v1/assignments/${assignmentId}/rubrics/`)
            .then(({ data }) => data, () => null);
        commit(types.UPDATE_ASSIGNMENT, {
            assignmentId,
            assignmentProps: { rubric },
        });
    },

    forceLoadSubmissions(context, assignmentId) {
        // This needs to be in one promise to make sure that two very quick
        // calls to `loadSubmissions` still only does one request (for the
        // same arguments of course).
        const promiseFun = async () => {
            await context.dispatch('loadCourses');

            if (context.getters.assignments[assignmentId] == null) {
                return;
            }

            await Promise.all([
                axios
                    .get(`/api/v1/assignments/${assignmentId}/submissions/?extended`)
                    .then(({ data: submissions }) => {
                        submissions.forEach(sub => {
                            sub.formatted_created_at = utils.readableFormatDate(sub.created_at);
                            sub.grade = utils.formatGrade(sub.grade);
                        });
                        return submissions;
                    }),
                axios
                    .get(`/api/v1/assignments/${assignmentId}/rubrics/`)
                    .then(({ data }) => data, () => null),
                axios
                    .get(`/api/v1/assignments/${assignmentId}/graders/`)
                    .then(({ data }) => data, () => null),
            ]).then(([submissions, rubric, graders]) => {
                context.commit(types.UPDATE_ASSIGNMENT, {
                    assignmentId,
                    assignmentProps: { submissions, rubric, graders },
                });
            });

            // It is possible that in the mean time these promises were
            // cleared. Simply store them again to prevent double loading.
            context.commit(types.SET_SUBMISSIONS_PROMISE, {
                assignmentId,
                promise: Promise.resolve(),
            });
        };

        const promise = promiseFun();
        context.commit(types.SET_SUBMISSIONS_PROMISE, {
            assignmentId,
            promise,
        });

        return promise;
    },

    async loadSubmissions(context, assignmentId) {
        if (context.state.submissionsLoaders[assignmentId] == null) {
            await context.dispatch('forceLoadSubmissions', assignmentId);
        }

        return context.state.submissionsLoaders[assignmentId];
    },

    updateSubmission({ commit }, { assignmentId, submissionId, submissionProps }) {
        commit(types.UPDATE_SUBMISSION, {
            assignmentId,
            submissionId,
            submissionProps,
        });
    },

    async reloadCourses({ commit }) {
        let courses;
        let perms;

        try {
            [{ data: courses }, { data: perms }] = await Promise.all([
                axios.get('/api/v1/courses/?extended=true'),
                axios.get('/api/v1/permissions/?type=course'),
            ]);
        } catch (_) {
            return commit(types.CLEAR_COURSES);
        }
        courses = courses.map(c => {
            c.permissions = perms[c.id];
            return c;
        });

        const [manageCourses, manageAssigs, createAssigs] = Object.entries(perms).reduce(
            ([course, assig, create], [key, val]) => {
                assig[key] = Object.entries(val).some(
                    ([k, v]) => MANAGE_ASSIGNMENT_PERMISSIONS.indexOf(k) !== -1 && v,
                );

                course[key] = Object.entries(val).some(
                    ([k, v]) => MANAGE_GENERAL_COURSE_PERMISSIONS.indexOf(k) !== -1 && v,
                );

                create[key] = Object.entries(val).some(
                    ([k, v]) => k === 'can_create_assignment' && v,
                );

                return [course, assig, create];
            },
            [{}, {}, {}],
        );

        return commit(types.SET_COURSES, [
            courses,
            manageCourses,
            manageAssigs,
            createAssigs,
            perms,
        ]);
    },

    updateCourse({ commit }, data) {
        commit(types.UPDATE_COURSE, data);
    },

    updateAssignment({ commit }, data) {
        commit(types.UPDATE_ASSIGNMENT, data);
    },
};

const mutations = {
    [types.SET_COURSES](state, [courses, manageCourses, manageAssigs, createAssigs, perms]) {
        state.submissionsLoaders = {};

        state.courses = courses.reduce((res, course) => {
            course.assignments.forEach(assignment => {
                const deadline = moment.utc(assignment.deadline, moment.ISO_8601).local();
                const reminderTime = moment.utc(assignment.reminder_time, moment.ISO_8601).local();
                let defaultReminderTime = deadline.clone().add(7, 'days');
                if (defaultReminderTime.isBefore(moment())) {
                    defaultReminderTime = moment().add(3, 'days');
                }

                assignment.course = course;
                assignment.deadline = utils.formatDate(assignment.deadline);
                assignment.created_at = utils.formatDate(assignment.created_at);
                assignment.canManage = manageAssigs[course.id];
                assignment.has_reminder_time = reminderTime.isValid();
                assignment.reminder_time = (reminderTime.isValid()
                    ? reminderTime
                    : defaultReminderTime
                ).format('YYYY-MM-DDTHH:mm');
            });

            course.permissions = perms[course.id];
            course.canManage = manageCourses[course.id];
            course.canCreateAssignments = createAssigs[course.id];

            res[course.id] = course;
            return res;
        }, {});
    },

    [types.CLEAR_COURSES](state) {
        state.courses = {};
        state.currentCourseLoader = null;
        state.submissionsLoaders = {};
    },

    [types.UPDATE_COURSE](state, { courseId, courseProps }) {
        const course = state.courses[courseId];

        if (course == null) {
            throw ReferenceError(`Could not find course: ${courseId}`);
        }

        Object.keys(courseProps).forEach(key => {
            if (!{}.hasOwnProperty.call(course, key) || key === 'id') {
                throw TypeError(`Cannot set course property: ${key}`);
            }

            Vue.set(course, key, courseProps[key]);
        });
    },

    [types.SET_COURSES_PROMISE](state, promise) {
        state.currentCourseLoader = promise;
    },

    [types.SET_SUBMISSIONS_PROMISE](state, { promise, assignmentId }) {
        Vue.set(state.submissionsLoaders, assignmentId, promise);
    },

    [types.UPDATE_ASSIGNMENT](state, { assignmentId, assignmentProps }) {
        const assignment = getAssignment(state, assignmentId);

        Object.keys(assignmentProps).forEach(key => {
            if (
                key !== 'submissions' &&
                key !== 'rubric' &&
                key !== 'graders' &&
                (!{}.hasOwnProperty.call(assignment, key) || key === 'id')
            ) {
                throw TypeError(`Cannot set assignment property: ${key}`);
            }

            Vue.set(assignment, key, assignmentProps[key]);
        });
    },

    [types.ADD_SUBMISSION](state, { assignmentId, submission }) {
        const assignment = getAssignment(state, assignmentId);

        Vue.set(assignment, 'submissions', [submission, ...(assignment.submissions || [])]);
    },

    [types.DELETE_SUBMISSION](state, { assignmentId, submissionId }) {
        const assignment = getAssignment(state, assignmentId);

        if (assignment.submissions != null) {
            Vue.set(
                assignment,
                'submissions',
                assignment.submissions.filter(sub => sub.id !== submissionId),
            );
        }
    },

    [types.UPDATE_SUBMISSION](state, { assignmentId, submissionId, submissionProps }) {
        const assignment = getAssignment(state, assignmentId);
        const l = assignment.submissions ? assignment.submissions.length : 0;

        for (let i = 0; i < l; i++) {
            if (assignment.submissions[i].id === submissionId) {
                Object.entries(submissionProps).forEach(([key, val]) => {
                    if (key === 'id') {
                        throw TypeError(`Cannot set submission property: ${key}`);
                    }
                    Vue.set(
                        assignment.submissions[i],
                        key,
                        key === 'grade' ? utils.formatGrade(val) : val,
                    );
                });
                return;
            }
        }

        throw ReferenceError('Submission not found');
    },
};

export default {
    namespaced: true,
    state: {
        courses: {},
        currentCourseLoader: null,
        submissionsLoaders: {},
    },

    getters,
    actions,
    mutations,
};
