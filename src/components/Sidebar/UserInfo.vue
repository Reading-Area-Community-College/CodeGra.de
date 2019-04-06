<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="sidebar-user-info">
    <b-card header="Preferences">
        <preference-manager :show-language="false"
                            :show-whitespace="false"
                            :show-revision="false"/>
    </b-card>

    <b-card header="User info">
        <user-info/>
    </b-card>

    <b-card class="snippets" v-if="snippets">
        <template slot="header">
            Snippets

            <description-popover>
                <template slot="description">
                    <p>
                        Edit your snippets here. When you type the name in a
                        field that supports snippets and then press
                        <kbd>Tab</kbd>, the typed name is replaced with the
                        snippet's replacement text.
                    </p>

                    <p>
                        To create a new snippet, click the <icon name="plus"/>.
                        In the popup you can set the name and replacement text
                        of the snippet. Snippet names may not contain spaces
                        and must be unique.
                    </p>

                    <p>
                        Click the <icon name="pencil"/> button to edit an
                        existing snippet.
                    </p>

                    <p>
                        Finally, <icon name="times"/> deletes a snippet.
                    </p>
                </template>
            </description-popover>
        </template>

        <snippet-manager/>
    </b-card>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/plus';

import UserInfo from '@/components/UserInfo';
import SnippetManager from '@/components/SnippetManager';
import PreferenceManager from '@/components/PreferenceManager';
import DescriptionPopover from '@/components/DescriptionPopover';

import { waitAtLeast } from '../../utils';

export default {
    name: 'sidebar-user-info',

    components: {
        Icon,
        UserInfo,
        SnippetManager,
        PreferenceManager,
        DescriptionPopover,
    },

    data() {
        return {
            snippets: false,
            oldSbloc: null,
        };
    },

    mounted() {
        this.$emit('loading');
        const done = this.$hasPermission('can_use_snippets').then(snippets => {
            this.snippets = snippets;
        });

        // Most components should be loaded by now.
        waitAtLeast(250, done).then(() => {
            this.$emit('loaded');
        });
    },

    async created() {
        await this.$nextTick();
        this.oldSbloc = this.$route.query.sbloc || undefined;
        if (this.oldSbloc === 'm') {
            this.oldSbloc = undefined;
        }
        this.$router.replace(this.getNewRoute('m'));
    },

    destroyed() {
        this.$router.replace(this.getNewRoute(this.oldSbloc));
    },

    methods: {
        getNewRoute(sbloc) {
            return Object.assign({}, this.$route, {
                query: Object.assign({}, this.$route.query, {
                    sbloc,
                }),
            });
        },
    },

    computed: {
        ...mapGetters('user', ['loggedIn']),
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';
.card {
    margin-bottom: 15px;

    &:last-child {
        margin-bottom: 0;
    }
}

.sidebar-user-info {
    overflow-y: auto;
    padding: 1rem;
    padding-bottom: 0;

    &::after {
        content: '';
        display: block;
        height: 1rem;
    }
}

.snippets .snippet-manager {
    margin: -1.25rem;
}
</style>
