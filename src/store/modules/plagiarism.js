/* SPDX-License-Identifier: AGPL-3.0-only */
import axios from 'axios';
import Vue from 'vue';

import * as types from '../mutation-types';

const LIMIT_FIRST_REQUEST = 250;
const LIMIT_PER_REQUEST = 100;

const getters = {
    runs: state => state.runs,
};

const processCase = (run, serverCase) => {
    if (serverCase.assignments[0].id !== run.assignment.id) {
        serverCase.assignments.reverse();
        serverCase.users.reverse();
        serverCase.submissions.reverse();
    }
    serverCase.canView =
        serverCase.submissions != null &&
        serverCase.assignments[0].id != null &&
        serverCase.assignments[1].id != null;
    if (serverCase.canView) {
        // eslint-disable-next-line
        serverCase._rowVariant = 'info';
    } else {
        // eslint-disable-next-line
        serverCase._rowVariant = 'warning';
    }
    return serverCase;
};

const actions = {
    loadRun({ state, commit }, runId) {
        if (state.loadRunPromises[runId] == null) {
            const promise = Promise.all([
                axios.get(`/api/v1/plagiarism/${runId}`),
                axios.get(`/api/v1/plagiarism/${runId}/cases/?limit=${LIMIT_FIRST_REQUEST}`),
            ]).then(([{ data: run }, { data: cases }]) => {
                run.cases = (cases || []).map(c => processCase(run, c));
                run.has_more_cases = run.cases.length >= LIMIT_FIRST_REQUEST;
                commit(types.SET_PLAGIARISM_RUN, run);
                return run;
            });
            commit(types.SET_PLAGIARISM_PROMISE, { runId, promise });
        }
        return state.loadRunPromises[runId];
    },

    async loadMoreCases({ state, commit }, runId) {
        await state.loadRunPromises[runId];
        const run = state.runs[runId];
        if (run.has_more_cases) {
            const { data: cases } = await axios.get(
                `/api/v1/plagiarism/${runId}/cases/?limit=${LIMIT_PER_REQUEST}&offset=${
                    state.runs[runId].cases.length
                }`,
            );

            commit(types.ADD_PLAGIARISM_CASES, {
                runId,
                newCases: cases.map(c => processCase(run, c)),
            });
        }
    },

    async refreshRun({ dispatch }, runId) {
        await dispatch('removeRun', runId);
        return dispatch('loadRun', runId);
    },

    removeRun({ commit }, runId) {
        commit(types.CLEAR_PLAGIARISM_RUN, runId);
    },

    clear({ commit }) {
        commit(types.CLEAR_PLAGIARISM_RUNS);
    },
};

const mutations = {
    [types.SET_PLAGIARISM_RUN](state, run) {
        Vue.set(state.runs, run.id, run || {});
    },

    [types.CLEAR_PLAGIARISM_RUN](state, runId) {
        Vue.set(state.runs, runId, undefined);
        Vue.set(state.loadRunPromises, runId, undefined);

        delete state.runs[runId];
        delete state.loadRunPromises[runId];
    },

    [types.ADD_PLAGIARISM_CASES](state, { runId, newCases }) {
        const run = state.runs[runId];
        run.cases = run.cases.concat(newCases);
        run.has_more_cases = newCases.length >= LIMIT_PER_REQUEST;
        Vue.set(state.runs, runId, run);
    },

    [types.SET_PLAGIARISM_PROMISE](state, { runId, promise }) {
        Vue.set(state.loadRunPromises, runId, promise);
    },

    [types.CLEAR_PLAGIARISM_RUNS](state) {
        state.runs = {};
        state.loadRunPromises = {};
    },
};

export default {
    namespaced: true,
    state: {
        runs: {},
        loadRunPromises: {},
    },
    getters,
    actions,
    mutations,
};
