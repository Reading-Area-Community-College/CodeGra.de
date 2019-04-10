<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="infinite-plagiarism-case-list">
    <slot name="default" :cases="filteredCases"/>

    <b-alert show
             variant="warning"
             v-if="run.has_more_cases && run.cases.length > 0 && filter">
        There might be more cases that match your search that are not yet loaded.
        Search for more cases by clicking on the button below. We have
        loaded {{ run.cases.length }} from the server, with a minimal average
        similarity of
        {{ run.cases[run.cases.length - 1].match_avg.toFixed(2) }}. Newly loaded
        cases will have a lower average similarity.
    </b-alert>
    <submit-button class="extra-load-btn"
                   ref="btn"
                   :disabled="!run.has_more_cases"
                   @after-success="afterLoadMoreCases(false)"
                   @after-error="afterLoadMoreCases(true)"
                   :duration="200"
                   :wait-at-least="0"
                   :submit="loadMoreCases">
        <span v-if="run.has_more_cases">
            Load more cases
        </span>
        <span v-else>
            No more cases.
        </span>
        <infinite-loading @infinite="infiniteTrigger"
                          v-if="!hadError"
                          :distance="skipNextInfinite === 0 ? undefined : -10000"
                          class="infinite-plagiarism-loader"
                          :identifier="infiniteId">
            <div slot="spinner"></div>
            <div slot="no-more"></div>
            <div slot="no-results"></div>
            <div slot="error" slot-scope="err">
                <p><span v-if="errorMsg">: {{ errorMsg }}</span></p>

                Click <b-btn variant="primary" size="sm"
                             @click="err.trigger">
                    here
                </b-btn> to retry.
            </div>
        </infinite-loading>
    </submit-button>
</div>
</template>

<script>
import { mapActions } from 'vuex';
import InfiniteLoading from 'vue-infinite-loading';

import { userMatches } from '@/utils';

import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'infinite-plagiarism-case-list',

    props: {
        run: {
            type: Object,
            required: true,
        },

        filter: {
            type: String,
            required: true,
        },
    },

    watch: {
        filteredCases(newVal, oldVal) {
            if (newVal.length !== oldVal.length) {
                this.temporarilyDisableLoader();
            }
        },
    },

    data() {
        return {
            hadError: false,
            errorMsg: '',
            state: null,
            infiniteId: +new Date(),
            skipNextInfinite: 0,
        };
    },

    computed: {
        filteredCases() {
            if (!this.filter) {
                return this.run.cases;
            }

            const filterParts = this.filter.toLocaleLowerCase().split(' ');

            return this.run.cases.filter(curCase =>
                filterParts.every(part => {
                    if (userMatches(curCase.users[0], part)) {
                        return true;
                    }
                    if (userMatches(curCase.users[1], part)) {
                        return true;
                    }
                    if (curCase.match_avg.toFixed(2).indexOf(part) > -1) {
                        return true;
                    }
                    return curCase.match_max.toFixed(2).indexOf(part) > -1;
                }),
            );
        },
    },

    methods: {
        ...mapActions('plagiarism', {
            loadMorePlagiarismCases: 'loadMoreCases',
        }),

        async temporarilyDisableLoader() {
            this.skipNextInfinite += 1;
            await this.$nextTick();
            setTimeout(() => {
                this.skipNextInfinite -= 1;
            }, 500);
        },

        loadMoreCases() {
            return this.loadMorePlagiarismCases(this.run.id);
        },

        afterLoadMoreCases(hadError) {
            this.hadError = hadError;
            if (this.state) {
                if (this.run.has_more_cases) {
                    this.state.loaded();
                } else {
                    this.state.complete();
                }
                this.state = null;
            }
        },

        async infiniteTrigger($state) {
            this.state = $state;
            this.$refs.btn.onClick();
            this.temporarilyDisableLoader();
        },
    },

    components: {
        InfiniteLoading,
        SubmitButton,
        Loader,
    },
};
</script>


<style lang="less" scoped>
.extra-load-btn {
    margin: 15px auto;
    display: block;
    max-width: 15rem;
}
</style>
