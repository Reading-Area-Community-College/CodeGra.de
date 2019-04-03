<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="manage-course">
    <local-header always-show-extra-slot>
        <b-form-fieldset class="filter-input">
            <input v-model="filter"
                    class="form-control"
                    placeholder="Type to Search"/>
        </b-form-fieldset>

        <template slot="extra">
            <category-selector
                v-if="course"
                slot="extra"
                class="cat-selector"
                v-model="selectedCat"
                default="Members"
                :categories="categories"/>
        </template>
    </local-header>

    <loader v-if="!course" page-loader/>
    <div class="content" v-else>
        <users-manager :class="{ hidden: selectedCat !== 'Members'}"
                       class="cat-wrapper"
                       v-if="membersEnabled"
                       :course="course"
                       :filter="filter"/>
        <permissions-manager :class="{ hidden: selectedCat !== 'Permissions' }"
                             v-if="permissionsEnabled"
                             class="cat-wrapper"
                             :course-id="course.id"
                             :filter="filter"/>
        <span :class="{ hidden: selectedCat !== 'Groups' }"
              v-if="groupsEnabled"
              class="cat-wrapper">
            <group-set-manager :course="course"/>
        </span>

        <span :class="{ hidden: selectedCat !== 'Snippets' }"
              class="cat-wrapper">
            <snippet-manager
                v-if="snippetsEnabled"
                :course="course"
                :editable="course.permissions.can_manage_course_snippets"/>
        </span>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import UsersManager from '@/components/UsersManager';
import PermissionsManager from '@/components/PermissionsManager';
import LocalHeader from '@/components/LocalHeader';
import Loader from '@/components/Loader';
import CategorySelector from '@/components/CategorySelector';
import GroupSetManager from '@/components/GroupSetManager';
import SnippetManager from '@/components/SnippetManager';

import { setPageTitle } from './title';

export default {
    name: 'manage-course-page',

    data() {
        return {
            selectedCat: '',
            filter: '',
        };
    },

    computed: {
        ...mapGetters('courses', ['courses']),

        course() {
            return this.courses[this.$route.params.courseId];
        },

        courseId() {
            return Number(this.$route.params.courseId);
        },

        membersEnabled() {
            return this.course && this.course.permissions.can_edit_course_users;
        },

        permissionsEnabled() {
            return this.course && this.course.permissions.can_edit_course_roles;
        },

        groupsEnabled() {
            return (
                UserConfig.features.groups &&
                this.course &&
                this.course.permissions.can_edit_group_set
            );
        },

        snippetsEnabled() {
            return (
                this.course &&
                (this.course.permissions.can_manage_course_snippets ||
                    this.course.permissions.can_view_course_snippets)
            );
        },

        categories() {
            return [
                {
                    name: 'Members',
                    enabled: this.membersEnabled,
                },
                {
                    name: 'Permissions',
                    enabled: this.permissionsEnabled,
                },
                {
                    name: 'Groups',
                    enabled: this.groupsEnabled,
                },
                {
                    name: 'Snippets',
                    enabled: this.snippetsEnabled,
                },
            ];
        },
    },

    async mounted() {
        await this.loadCourses();
    },

    watch: {
        course() {
            setPageTitle(this.course.name);
        },
    },

    methods: {
        ...mapActions('courses', ['loadCourses']),
    },

    components: {
        UsersManager,
        PermissionsManager,
        LocalHeader,
        Loader,
        CategorySelector,
        GroupSetManager,
        SnippetManager,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.manage-course {
    display: flex;
    flex-direction: column;
}
.manage-course > .content {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
}

.filter-input {
    flex: 1 1 auto;
    margin-bottom: 0;
}

.cat-wrapper {
    transition: opacity @transition-duration ease-out;
    height: 100%;
    padding-top: 5px;

    &.hidden {
        height: 0;
        overflow: hidden;
        padding: 0;
        transition: none;
        opacity: 0;
        max-height: 0;
    }
}
</style>
