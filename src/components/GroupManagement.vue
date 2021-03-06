<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="group-management">
    <b-card class="group-card">
        <b-input-group v-if="editingGroup" class="title-edit card-header">
            <input class="form-control"
                   v-model="newTitle"
                   @keyup.ctrl.enter="$refs.submitTitle.onClick"/>
            <b-input-group-append>
                <submit-button :submit="cancelEditTitle"
                               variant="warning"
                               v-b-popover.top.hover="'Cancel'">
                    <icon name="times"/>
                </submit-button>
                <submit-button ref="submitTitle"
                               :submit="updateTitle"
                               @after-success="afterUpdateTitle"
                               v-b-popover.top.hover="'Save'">
                    <icon name="check"/>
                </submit-button>
            </b-input-group-append>
        </b-input-group>
        <template slot="header" :class="{'title-edit-wrapper': editingGroup}" v-else>
            <div class="title-display">
                <span>
                    <b>Group "{{ group.name }}"</b> ({{ group.members.length }} / {{ groupSet.maximum_size }})
                </span>
                <div class="pencil"
                     v-if="canEdit"
                     @click="editingGroup = true;"
                     v-b-popover.top.hover="'Edit or delete group'"
                     >
                    <icon name="pencil"/>
                </div>
            </div>
        </template>
        <masonry :cols="{default: 3, [$root.largeWidth]: 2, [$root.mediumWidth]: 1 }"
                 :gutter="30"
                 class="outer-block">
            <div v-for="user, i in group.members"
                 class="user-box"
                 :key="`assignment-group-${group.id}-member-${user.id}`">
                <div style="display: flex">
                    <span>{{ user.name }} ({{ user.username }})</span>
                    <span class="lti-progress" style="" v-if="showLtiProgress">
                        <div  v-b-popover.top.click.html="ltiTexts.done(user)" v-if="memberStates[user.id] && 0">
                            <icon style="margin-top: 1px" name="check"/>
                        </div>
                        <loader :scale="1" v-b-popover.top.click.html="ltiTexts.loading(user)" v-else/>
                    </span>
                </div>
                <submit-button v-if="canEdit && (myId === user.id || canEditOthers)"
                               class="delete"
                               :delay="3000"
                               :submit="() => removeUser(i)"
                               @after-success="afterRemoveUser"
                               :confirm="`Are you sure you want to remove ${myId
                                         === user.id ? 'yourself' : user.name} from this group?`"
                               v-b-popover.top.hover="'Remove from group'">
                    <icon name="times"/>
                </submit-button>
            </div>
        </masonry>
        <span class="outer-block no-user-placeholder"
              v-if="group.members.length <= 0">
            No members
        </span>
        <!-- Use a show so the ref is always available -->
        <div v-show="editingGroup"
             v-b-popover.top.hover="deleteGroupDisabled ? 'You do not have permission to delete this group as it contains other users.' : ''">
            <b-input-group>
                <submit-button label="Delete group"
                               :disabled="deleteGroupDisabled"
                               style="pointer-events: initial;"
                               variant="danger"
                               confirm="Are you sure you want to delete this group?"
                               class="full-width-button"
                               :submit="deleteGroup"
                               @after-success="afterDeleteGroup"/>
            </b-input-group>
        </div>
        <div v-b-popover.top.hover="groupFull ? 'This group is full' : ''"
             v-show="!editingGroup">
            <b-input-group class="new-user-wrapper"
                           v-if="canEditOthers">
                <user-selector placeholder="Type to add a member"
                               :filter-students="filterMembers"
                               :disabled="groupFull"
                               v-model="newAuthor"
                               :base-url="`/api/v1/courses/${course.id}/users/`"/>
                <template slot="append">
                    <submit-button label="Add"
                                   :disabled="groupFull || !newAuthor"
                                   :submit="() => addUser(newAuthor.username)"
                                   @success="afterAddUser"/>
                </template>
            </b-input-group>
            <submit-button v-else-if="canEditOwn && !selectedMembers.has(myId)"
                           label="Join"
                           :disabled="groupFull"
                           class="full-width-button"
                           :submit="() => addUser(myUsername)"
                           @success="afterAddUser">
                Join
            </submit-button>
        </div>
    </b-card>
</div>
</template>

<script>
import { mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/pencil';

import SubmitButton from './SubmitButton';
import Loader from './Loader';
import UserSelector from './UserSelector';

// Reload every 10 seconds.
const timeoutTime = 10000;

export default {
    props: {
        value: {
            type: Object,
            required: true,
        },

        selectedMembers: {
            type: Set,
            required: true,
        },

        groupSet: {
            type: Object,
            required: true,
        },

        course: {
            type: Object,
            required: true,
        },

        assignment: {
            type: Object,
            default: null,
        },

        showLtiProgress: {
            type: Boolean,
            default: false,
        },

        canEditOwn: {
            type: Boolean,
            required: true,
        },

        canEditOthers: {
            type: Boolean,
            required: true,
        },
    },

    data() {
        const group = Object.assign({}, this.value);
        group.members = group.members.map(o => Object.assign({}, o));
        group.user_states = Object.assign({}, group.user_states);

        return {
            group,
            newAuthor: null,
            editingGroup: false,
            newTitle: group.name,
            compDestroyed: false,
            updateStates: null,
            memberStates: {},
        };
    },

    mounted() {
        if (this.showLtiProgress) {
            this.reloadGroupStates();
        }
    },

    watch: {
        showLtiProgress(newVal) {
            if (newVal) {
                this.updateStates = setTimeout(this.reloadGroupStates, timeoutTime);
            }
        },
    },

    destroyed() {
        if (this.updateStates) {
            clearTimeout(this.updateStates);
            this.updateStates = null;
        }
        this.compDestroyed = true;
    },

    computed: {
        ...mapGetters('user', { myId: 'id', myUsername: 'username' }),

        groupFull() {
            return this.group.members.length >= this.groupSet.maximum_size;
        },

        ltiTexts() {
            const divStart = '<div style="text-align: justify">';
            const divEnd = '</div>';
            const { myId } = this;

            const makeName = user => (myId === user.id ? 'You' : this.$htmlEscape(user.name));
            const lmsName = this.$htmlEscape(this.assignment.lms_name);

            const loading = user => `${divStart}We cannot submit the
submission. ${makeName(user)} should open the assignment through
${lmsName} to resolve this issue.${divEnd}`;

            const done = () => `${divStart}We can submit the submission. No
action is required.${divEnd}`;

            return {
                loading,
                done,
            };
        },

        canEdit() {
            let own = false;
            if (this.group.members.some(m => m.id === this.myId)) {
                own = this.canEditOwn;
            }
            return own || this.canEditOthers;
        },

        deleteGroupDisabled() {
            return !this.canEdit || (this.group.members.length > 1 && !this.canEditOthers);
        },
    },

    methods: {
        reloadGroupStates() {
            // setInterval is not used as this might cause a large load on the
            // server. Now we know there is `timeoutTime` between each request.
            this.$http
                .get(
                    `/api/v1/group_sets/${this.assignment.id}/groups/${
                        this.group.id
                    }/member_states/`,
                )
                .then(({ data }) => {
                    this.memberStates = data;
                    this.updateStates = null;
                    if (this.showLtiProgress && !this.compDestroyed) {
                        this.updateStates = setTimeout(this.reloadGroupStates, timeoutTime);
                    }
                });
        },

        cancelEditTitle() {
            this.editingGroup = false;
            this.newTitle = this.group.name;
            return Promise.resolve();
        },

        updateTitle() {
            return this.$http.post(`/api/v1/groups/${this.group.id}/name`, {
                name: this.newTitle,
            });
        },

        afterUpdateTitle(response) {
            this.editingGroup = false;
            this.group = response.data;
            this.newTitle = this.group.name;
            this.$emit('input', this.group);
        },

        removeUser(i) {
            const user = this.group.members[i];
            return this.$http.delete(`/api/v1/groups/${this.group.id}/members/${user.id}`);
        },

        afterRemoveUser(response) {
            this.group = response.data;
            this.$emit('input', this.group);
        },

        filterMembers(user) {
            return !this.selectedMembers.has(user.id);
        },

        addUser(username) {
            return this.$http.post(`/api/v1/groups/${this.group.id}/member`, { username });
        },

        afterAddUser(response) {
            this.newAuthor = null;
            this.group = response.data;
            this.$emit('input', this.group);
        },

        deleteGroup() {
            return this.$http.delete(`/api/v1/groups/${this.group.id}`);
        },

        afterDeleteGroup() {
            this.group = undefined;
            this.$emit('input', undefined);
        },
    },

    components: {
        SubmitButton,
        UserSelector,
        Loader,
        Icon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.title-edit {
    padding: 0;
    margin-top: -1.25rem;
    margin-bottom: 1.25rem;
    .form-control {
        border-bottom-left-radius: 0;
        border: 0;
    }
    .input-group-append .btn {
        border-bottom-right-radius: 0;
    }
}
.title-display {
    display: flex;
    justify-content: space-between;
    vertical-align: center;
    .pencil {
        cursor: pointer;
    }
}

.card-body {
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
}

.new-user-wrapper.input-group {
    .btn {
        border-top-right-radius: 0;
    }
}

.outer-block {
    padding-left: 1.25rem;
    padding-right: 1.25rem;
}

.user-box {
    margin-bottom: 1rem;
    padding: 5px 10px;
    background: @color-secondary;
    color: white;
    #app.dark & .delete,
    #app.dark & {
        color: @color-lighter-gray;
    }

    border-radius: 0.25rem;
    border: 1px solid @color-secondary;
    display: flex;
    justify-content: space-between;
    vertical-align: center;
    .delete {
        border: 0 !important;
        box-shadow: none !important;
        background: none !important;
        padding: 0;
        &.btn-danger {
            color: @alert-danger-color;
        }
    }
}

.no-user-placeholder {
    display: block;
    text-align: center;
    margin-bottom: 1rem;
    color: gray;
    #app.dark & {
        color: @color-light-gray;
    }
}

.lti-progress {
    justify-content: center;
    display: flex;
    margin-left: 5px;
    cursor: help;
}

.full-width-button {
    width: 100%;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
}
</style>

<style lang="less">
.group-management .user-selector.multiselect .multiselect__tags {
    border-left: 0;
    border-bottom: 0;
    border-top-left-radius: 0;
}

.group-management .user-selector.multiselect--active .multiselect__tags {
    border-bottom-left-radius: 0.25rem;
}
</style>
