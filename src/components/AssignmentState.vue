<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="assignment-state" v-if="editable">
    <b-button-group>
        <submit-button class="state-button larger"
                       v-if="canManageLTIState"
                       :variant="ltiHiddenOpenVariant"
                       v-b-popover.window.top.hover="`Hidden or open, managed by ${lmsName}`"
                       :submit="() => updateState(states.OPEN)"
                       @success="afterUpdateState"
                       :duration="0"
                       confirm="Students will not be able to see their grade.
                       whether they can see the assignment at all is determined
                       by the assignment's state in ${lmsName}.">
            <icon :name="icons[states.HIDDEN]"/>
            <icon :name="icons[states.OPEN]"/>
        </submit-button>

        <b-button-group v-else>
            <submit-button class="state-button"
                           :variant="hiddenVariant"
                           v-b-popover.window.top.hover="labels[states.HIDDEN]"
                           :submit="() => updateState(states.HIDDEN)"
                           @success="afterUpdateState"
                           :duration="0"
                           confirm="Students will not be able to view the
                           assignment. Are you sure?">
                <icon :name="icons[states.HIDDEN]"/>
            </submit-button>

            <submit-button class="state-button"
                           :variant="openVariant"
                           v-b-popover.window.top.hover="labels[states.OPEN]"
                           :submit="() => updateState(states.OPEN)"
                           @success="afterUpdateState"
                           :duration="0"
                           confirm="Students will be able to see the assignment
                           and submit work if the deadline has not passed yet,
                           but they will not be able to see their grade. Are
                           you sure?">
                <icon :name="icons[states.OPEN]"/>
            </submit-button>
        </b-button-group>

        <submit-button class="state-button"
                       :variant="doneVariant"
                       v-b-popover.window.top.hover="labels[states.DONE]"
                       :submit="() => updateState(states.DONE)"
                       @success="afterUpdateState"
                       :duration="0"
                       confirm="Students will be able to see their grade. Are
                       you sure?">
            <icon :name="icons[states.DONE]"/>
        </submit-button>
    </b-button-group>
</div>
<icon :name="icons[assignment.state]"
      class="assignment-state state-icon"
      v-b-popover.window.top.hover="labels[assignment.state]"
      v-else/>
</template>

<script>
import { mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/eye-slash';
import 'vue-awesome/icons/clock-o';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/check';

import ltiProviders from '@/lti_providers';

import * as states from '../store/assignment-states';

import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'assignment-state',

    props: {
        assignment: {
            type: Object,
            default: null,
        },

        editable: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            states,
            labels: {
                [states.HIDDEN]: 'Hidden',
                [states.SUBMITTING]: 'Submitting',
                [states.GRADING]: 'Grading',
                [states.OPEN]: 'Open',
                [states.DONE]: 'Done',
            },
            icons: {
                [states.HIDDEN]: 'eye-slash',
                [states.SUBMITTING]: 'clock-o',
                [states.GRADING]: 'pencil',
                [states.OPEN]: 'clock-o',
                [states.DONE]: 'check',
            },
        };
    },

    computed: {
        ltiHiddenOpenVariant() {
            const st = this.assignment.state;
            return st !== states.DONE ? 'primary' : 'outline-primary';
        },

        hiddenVariant() {
            const st = this.assignment.state;
            return st === states.HIDDEN ? 'danger' : 'outline-danger';
        },

        openVariant() {
            const st = this.assignment.state;
            return st === states.SUBMITTING || st === states.GRADING || st === states.OPEN
                ? 'warning'
                : 'outline-warning';
        },

        doneVariant() {
            const st = this.assignment.state;
            return st === states.DONE ? 'success' : 'outline-success';
        },

        canManageLTIState() {
            return this.assignment.is_lti && ltiProviders[this.lmsName].supportsStateManagement;
        },

        lmsName() {
            return this.assignment.lms_name;
        },
    },

    methods: {
        ...mapActions('courses', ['updateAssignment']),

        updateState(pendingState) {
            return this.$http
                .patch(`/api/v1/assignments/${this.assignment.id}`, {
                    state: pendingState,
                })
                .then(() => pendingState);
        },

        afterUpdateState(pendingState) {
            this.updateAssignment({
                assignmentId: this.assignment.id,
                assignmentProps: {
                    state: pendingState,
                },
            });
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
.state-button .fa-icon {
    transform: translateY(1px) !important;
}

.state-button.larger {
    width: 4em;

    .fa-icon {
        margin-left: 0;
    }
}
</style>
