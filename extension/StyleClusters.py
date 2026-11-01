"""UNO component behind the Tools ▸ Style Clusters… menu entry."""
import traceback

import unohelper
from com.sun.star.task import XJobExecutor

IMPL = "org.nohwayjose.styleclusters.Launcher"


class Launcher(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    def trigger(self, args):
        try:
            from styleclusters import dialog  # lives in pythonpath/
            desktop = self.ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
            dialog.open_for(self.ctx, desktop.getCurrentComponent())
        except Exception:
            traceback.print_exc()


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Launcher, IMPL, ("com.sun.star.task.Job",))
