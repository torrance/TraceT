import rules


@rules.predicate
def is_trigger_owner(user, trigger):
    return trigger.user == user


rules.add_perm(
    "tracet.view_trigger",
    rules.is_group_member("astronomers") | rules.is_group_member("admin"),
)
rules.add_perm(
    "tracet.add_trigger",
    rules.is_group_member("admin") | rules.is_group_member("astronomers"),
)
rules.add_perm("tracet.admin_triggers", rules.is_group_member("admin"))
rules.add_perm(
    "tracet.change_trigger", rules.is_group_member("admin") | is_trigger_owner
)
rules.add_perm(
    "tracet.delete_trigger", rules.is_group_member("admin") | is_trigger_owner
)
rules.add_perm(
    "tracet.retrigger_trigger", rules.is_group_member("admin") | is_trigger_owner
)
