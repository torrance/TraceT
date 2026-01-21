import rules


@rules.predicate
def is_trigger_owner(user, trigger):
    return trigger.user == user

@rules.predicate
def always(user):
    print("Hi there!")
    return False


# Trigger permissions
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

# User administration permissions
rules.add_perm("auth", rules.is_group_member("admin"))
rules.add_perm(
    "auth.view_user", rules.is_group_member("admin")
)
rules.add_perm(
    "auth.add_user", rules.is_group_member("admin")
)
rules.add_perm(
    "auth.change_user", rules.is_group_member("admin")
)
rules.add_perm(
    "auth.delete_user", rules.is_group_member("admin")
)
