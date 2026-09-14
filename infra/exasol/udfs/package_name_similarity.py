from sss_core.repositories.similarity import package_name_similarity


def run(ctx):
    ctx.emit(package_name_similarity(ctx.left_name, ctx.right_name))
