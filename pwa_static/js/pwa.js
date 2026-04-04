(function () {
    var serviceWorkerUrl = "/static/js/service-worker.js";
    var installBanner = document.getElementById("pwaInstallBanner");
    var installButton = document.getElementById("pwaInstallButton");
    var dismissButton = document.getElementById("pwaDismissButton");
    var deferredPrompt = null;

    var isStandalone = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
    if (window.navigator.standalone) {
        isStandalone = true;
    }

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
            navigator.serviceWorker.register(serviceWorkerUrl).catch(function () {
                return null;
            });
        });
    }

    if (!installBanner || !installButton || isStandalone) {
        return;
    }

    var hideBanner = function () {
        installBanner.hidden = true;
    };

    var showBanner = function () {
        installBanner.hidden = false;
    };

    if (dismissButton) {
        dismissButton.addEventListener("click", hideBanner);
    }

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredPrompt = event;
        showBanner();
    });

    window.addEventListener("appinstalled", function () {
        deferredPrompt = null;
        hideBanner();
    });

    installButton.addEventListener("click", function () {
        if (!deferredPrompt) {
            return;
        }

        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
            deferredPrompt = null;
            hideBanner();
        });
    });
}());
