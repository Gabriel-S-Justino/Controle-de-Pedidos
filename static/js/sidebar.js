(function () {
    "use strict";

    const body = document.body;
    const sidebarToggle = document.getElementById("sidebarToggle");
    const mobileToggle = document.getElementById("sidebarMobileToggle");
    const backdrop = document.getElementById("sidebarBackdrop");

    if (!sidebarToggle || !mobileToggle) return;

    const STORAGE_KEY = "cnp.sidebar.collapsed";

    function isMobile() {
        return window.matchMedia("(max-width: 760px)").matches;
    }

    function setCollapsed(collapsed) {
        if (isMobile()) return;

        body.classList.toggle("sidebar-collapsed", collapsed);
        sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        sidebarToggle.setAttribute(
            "aria-label",
            collapsed ? "Expandir menu" : "Recolher menu"
        );
        sidebarToggle.setAttribute(
            "title",
            collapsed ? "Expandir menu" : "Recolher menu"
        );

        try {
            localStorage.setItem(STORAGE_KEY, String(collapsed));
        } catch (_) {
            // Preferência visual; falha de localStorage não deve quebrar a navegação.
        }
    }

    function closeMobile() {
        body.classList.remove("sidebar-mobile-open");
        mobileToggle.setAttribute("aria-expanded", "false");
    }

    function openMobile() {
        body.classList.add("sidebar-mobile-open");
        mobileToggle.setAttribute("aria-expanded", "true");
    }

    try {
        setCollapsed(localStorage.getItem(STORAGE_KEY) === "true");
    } catch (_) {
        setCollapsed(false);
    }

    sidebarToggle.addEventListener("click", function () {
        setCollapsed(!body.classList.contains("sidebar-collapsed"));
    });

    mobileToggle.addEventListener("click", function () {
        if (body.classList.contains("sidebar-mobile-open")) {
            closeMobile();
        } else {
            openMobile();
        }
    });

    if (backdrop) {
        backdrop.addEventListener("click", closeMobile);
    }

    document.querySelectorAll("#appSidebar a, #appSidebar button").forEach(function (item) {
        item.addEventListener("click", function () {
            if (isMobile() && item !== mobileToggle) {
                closeMobile();
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeMobile();
    });

    window.addEventListener("resize", function () {
        if (!isMobile()) {
            closeMobile();
        }
    });
})();
