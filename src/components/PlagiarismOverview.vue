<template>
<div v-if="error"
     class="plagiarism-overview">
    <b-alert show
             variant="danger"
             style="margin-top: 1rem;">
        {{ error }}
    </b-alert>
</div>
<loader v-else-if="loadingData || assignment == null"/>
<div class="plagiarism-overview" v-else>
    <local-header :title="`Plagiarism overview for assignment &quot;${assignment.name}&quot; of &quot;${assignment.course.name}&quot;`">
        <input v-model="filter"
               class="filter-input form-control"
               placeholder="Filter students"/>
    </local-header>

    <b-table :fields="tableFields"
             striped
             show-empty
             :sort-compare="sortCompareTable"
             sort-by="match_avg"
             sort-desc
             :items="filteredEntries"
             @row-clicked="rowClicked"
             @row-hovered="rowHovered"
             @mouseleave.native="rowHovered(null)"
             class="overview-table">
        <template slot="user1" slot-scope="row">
            <span v-if="row.item.assignments[0].id == assignmentId">
                {{ row.item.users[0].name }}
            </span>
            <span v-else>
                {{ row.item.users[1].name }}
            </span>
        </template>

        <template slot="user2" slot-scope="row">
            <span v-if="row.item.assignments[1].id == assignmentId && row.item.assignments[0].id == assignmentId">
                {{ row.item.users[1].name }}
            </span>
            <span v-else-if="row.item.assignments[1].id != assignmentId">
                {{ row.item.users[1].name }} <sup v-b-popover.hover.top="getOtherAssignmentDesc(row.item, 1)"
                                                  class="description"
                                                  >*</sup>
            </span>
            <span v-else>
                {{ row.item.users[0].name }} <sup v-b-popover.hover.top="getOtherAssignmentDesc(row.item, 0)"
                                                  class="description"
                                                  >*</sup>
            </span>
        </template>

        <template slot="empty">
            <div style="text-align: center;">
                <span v-if="overview.length == 0">No plagiarism found</span>
                <span v-else>No results found</span>
            </div>
        </template>
    </b-table>

    <b-popover v-if="disabledPopoverRowId"
               :target="disabledPopoverRowId"
               ref="disabledPopover"
               placement="top"
               show>
        {{ disabledPopoverContent }}
    </b-popover>
</div>
</template>

<script>
import moment from 'moment';
import 'vue-awesome/icons/asterisk';

import { mapActions, mapGetters } from 'vuex';

import { Loader, LocalHeader, DescriptionPopover } from '@/components';

export default {
    name: 'plagiarism-overview',

    data() {
        return {
            overview: null,
            filter: '',
            tableFields: [{
                key: 'user1',
                sortable: true,
                label: 'Student 1',
            }, {
                key: 'user2',
                sortable: true,
                label: 'Student 2',
            }, {
                key: 'match_max',
                sortable: true,
                label: 'Maximum score',
                formatter: item => item.toFixed(2),
            }, {
                key: 'match_avg',
                sortable: true,
                label: 'Average score',
                formatter: item => item.toFixed(2),
            }],
            loadingData: true,
            error: '',
            disabledPopoverRowId: '',
            disabledPopoverContent: '',
        };
    },

    computed: {
        ...mapGetters('courses', ['assignments']),

        plagiarismRunId() {
            return this.$route.params.plagiarismRunId;
        },

        assignmentId() {
            return this.$route.params.assignmentId;
        },

        assignment() {
            return this.assignments[this.assignmentId];
        },

        filteredEntries() {
            const filter = new RegExp(this.filter, 'i');

            return this.overview.filter(
                entry => entry.users[0].name.match(filter) ||
                    entry.users[1].name.match(filter),
            );
        },
    },

    watch: {
        $route(newRoute, oldRoute) {
            if (
                newRoute.params.assignmentId !== oldRoute.params.assignmentId ||
                newRoute.params.plagiarismRunId !== oldRoute.params.plagiarismRunId
            ) {
                this.loadOverview();
            }
        },
    },

    methods: {
        ...mapActions('courses', ['loadCourses']),

        rowClicked(item) {
            if (!this.canViewCase(item)) {
                return;
            }

            this.$router.push({
                name: 'plagiarism_detail',
                params: Object.assign(this.$route.params, {
                    plagiarismCaseId: item.id,
                }),
            });
        },

        rowHovered(item, _, event) {
            this.disabledPopoverRowId = '';

            if (item == null || this.canViewCase(item)) {
                return;
            }

            if (!event.target.id) {
                event.target.id = `row-${item.id}`;
            }

            const index = item.assignments[0].id === this.assignmentId ? 1 : 0;

            this.disabledPopoverContent = `You don't have the
            \`can_view_plagiarism\` permission on the course
            "${item.assignments[index].course.name}" to view this case.`;

            this.$nextTick(() => {
                this.disabledPopoverRowId = event.target.id;
            });
        },

        sortCompareTable(a, b, key) {
            if (key === 'user1' || key === 'user2') {
                const index = key === 'user1' ? 0 : 1;
                return a.users[index].name.localeCompare(
                    b.users[index].name, undefined, {
                        numeric: true,
                    },
                );
            }
            if (typeof a[key] === 'number' && typeof b[key] === 'number') {
                // If both compared fields are native numbers
                return a[key] - b[key];
            } else {
                // Stringify the field data and use String.localeCompare
                return a[key].localeCompare(b[key], undefined, {
                    numeric: true,
                });
            }
        },

        loadOverview() {
            this.loadingData = true;

            this.$http.get(
                `/api/v1/plagiarism/${this.plagiarismRunId}/cases/`,
            ).then(
                ({ data }) => {
                    for (let i = 0, l = data.length; i < l; i++) {
                        if (this.canViewCase(data[i])) {
                            // eslint-disable-next-line
                            data[i]._rowVariant = 'info';
                        } else {
                            // eslint-disable-next-line
                            data[i]._rowVariant = 'warning';
                        }
                    }

                    this.overview = data;
                },
                (err) => {
                    this.error = err.response.data.message;
                },
            ).then(
                () => { this.loadingData = false; },
            );
        },

        getOtherAssignmentDesc(item, index) {
            let desc = `This assignment was submitted to the assignment "${item.assignments[index].name}" of "${item.assignments[index].course.name}"`;

            if (item.submissions != null) {
                const date = moment.utc(item.submissions[index].created_at, moment.ISO_8601).local().format('YYYY-MM-DD');
                desc = `${desc} on ${date}`;
            }

            return desc;
        },

        canViewCase(item) {
            return item.submissions != null &&
                item.assignments[0].id != null &&
                item.assignments[1].id != null;
        },
    },

    mounted() {
        this.loadOverview();
    },

    components: {
        LocalHeader,
        Loader,
        DescriptionPopover,
    },
};
</script>

<style lang="less" scoped>
.filter-input {
    flex: 1 1 auto;
    width: auto;
    margin-left: 1rem;
}

.description {
    cursor: help;
}
</style>

<style lang="less">
@import "~mixins.less";

.plagiarism-overview .overview-table {
    .table-info,
    .table-warning {
        background-color: transparent !important;

        td {
            background-color: transparent !important;
        }

        &:nth-of-type(odd) {
            background-color: rgba(0, 0, 0, .05) !important;
        }
    }

    .table-info {
        cursor: pointer;

        &:hover {
            background-color: rgba(0, 0, 0, .075) !important;
        }
    }

    .table-warning {
        color: @color-secondary-text-lighter;
    }
}
</style>
