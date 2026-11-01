"""Start a private headless LibreOffice and talk to it over a pipe.
Uses its own user profile so it never collides with a running office."""
import os
import subprocess
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue


class Office:
    def __init__(self, profile=None, pipe=None):
        self.profile = profile or tempfile.mkdtemp(prefix="styleclusters-lo-")
        self.pipe = pipe or f"styleclusters{os.getpid()}"
        self.proc = subprocess.Popen(
            ["soffice", "--headless", "--invisible", "--norestore", "--nologo",
             f"-env:UserInstallation={uno.systemPathToFileUrl(self.profile)}",
             f"--accept=pipe,name={self.pipe};urp;"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(120):
            try:
                self.ctx = resolver.resolve(
                    f"uno:pipe,name={self.pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("LibreOffice did not start")
        self.desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)

    def load(self, path, hidden=True):
        pv = PropertyValue()
        pv.Name, pv.Value = "Hidden", hidden
        doc = self.desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(os.path.abspath(path)), "_blank", 0, (pv,))
        if doc is None:
            raise RuntimeError(f"Could not load {path} (open elsewhere? check for a .~lock file)")
        return doc

    def close(self):
        try:
            self.desktop.terminate()
        except Exception:
            pass
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
