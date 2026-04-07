(function () {
    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(";").shift();
        }
        return "";
    }

    function updateNotificationCount(nextCount) {
        const badge = document.getElementById("topbarNotificationCount");
        if (!badge) {
            return;
        }
        const count = Number(nextCount) || 0;
        badge.textContent = String(count);
        badge.classList.toggle("is-hidden", count <= 0);
    }

    function postJSON(url) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "XMLHttpRequest",
            },
        }).then((response) => {
            if (!response.ok) {
                throw new Error("Request failed");
            }
            return response.json();
        });
    }

    document.addEventListener("click", function (event) {
        const markButton = event.target.closest(".js-mark-notification-read");
        if (markButton) {
            const url = markButton.getAttribute("data-url");
            if (!url) {
                return;
            }
            event.preventDefault();
            postJSON(url)
                .then((data) => {
                    updateNotificationCount(data.unread_count);
                    const item = markButton.closest(".notification-item, tr");
                    if (item) {
                        item.classList.remove("is-unread", "notification-row-unread");
                    }
                    markButton.remove();
                })
                .catch(function () {});
            return;
        }

        const markAllButton = event.target.closest(".js-mark-all-notifications");
        if (markAllButton) {
            const url = markAllButton.getAttribute("data-url");
            if (!url) {
                return;
            }
            event.preventDefault();
            postJSON(url)
                .then((data) => {
                    updateNotificationCount(data.unread_count);
                    document.querySelectorAll(".notification-item").forEach(function (item) {
                        item.classList.remove("is-unread");
                    });
                    document.querySelectorAll(".notification-row-unread").forEach(function (row) {
                        row.classList.remove("notification-row-unread");
                    });
                    document.querySelectorAll(".js-mark-notification-read").forEach(function (button) {
                        button.remove();
                    });
                })
                .catch(function () {});
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        const form = document.getElementById("quickSearchForm");
        const input = document.getElementById("quickSearchInput");
        const panel = document.getElementById("quickSearchResults");
        if (!form || !input || !panel) {
            return;
        }

        const endpoint = form.getAttribute("data-search-url");
        let debounceTimer = null;
        let activeIndex = -1;

        function clearPanel() {
            panel.hidden = true;
            panel.innerHTML = "";
            activeIndex = -1;
        }

        function renderResults(items) {
            if (!Array.isArray(items) || items.length === 0) {
                panel.innerHTML = '<div class="search-result-empty">No results found.</div>';
                panel.hidden = false;
                return;
            }

            panel.innerHTML = items
                .map(function (item, idx) {
                    const href = item.href || "#";
                    const icon = item.icon || "bi bi-search";
                    const label = item.label || "Result";
                    const description = item.description || "";
                    return (
                        '<a class="search-result-item" data-result-index="' +
                        idx +
                        '" href="' +
                        escapeHtml(href) +
                        '">' +
                        '<span class="search-result-icon"><i class="' +
                        escapeHtml(icon) +
                        '"></i></span>' +
                        '<span class="search-result-copy">' +
                        '<p class="search-result-label">' +
                        escapeHtml(label) +
                        "</p>" +
                        '<p class="search-result-meta">' +
                        escapeHtml(description) +
                        "</p>" +
                        "</span>" +
                        "</a>"
                    );
                })
                .join("");
            panel.hidden = false;
        }

        function setActiveItem(index) {
            const items = panel.querySelectorAll(".search-result-item");
            if (!items.length) {
                activeIndex = -1;
                return;
            }
            if (index < 0) {
                index = items.length - 1;
            }
            if (index >= items.length) {
                index = 0;
            }
            activeIndex = index;
            items.forEach(function (item, idx) {
                item.classList.toggle("is-active", idx === activeIndex);
            });
            items[activeIndex].scrollIntoView({ block: "nearest" });
        }

        function fetchResults(value) {
            if (!endpoint) {
                return;
            }
            const query = value.trim();
            if (query.length < 2) {
                clearPanel();
                return;
            }

            fetch(endpoint + "?q=" + encodeURIComponent(query), {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Search failed");
                    }
                    return response.json();
                })
                .then(function (data) {
                    renderResults(data.results || []);
                })
                .catch(function () {
                    panel.innerHTML = '<div class="search-result-empty">Search temporarily unavailable.</div>';
                    panel.hidden = false;
                });
        }

        input.addEventListener("input", function () {
            const value = input.value;
            window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(function () {
                fetchResults(value);
            }, 260);
        });

        input.addEventListener("keydown", function (event) {
            if (panel.hidden) {
                return;
            }
            if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveItem(activeIndex + 1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveItem(activeIndex - 1);
            } else if (event.key === "Enter") {
                const activeItem = panel.querySelector(".search-result-item.is-active");
                if (activeItem) {
                    event.preventDefault();
                    window.location.href = activeItem.getAttribute("href");
                }
            } else if (event.key === "Escape") {
                clearPanel();
            }
        });

        document.addEventListener("click", function (event) {
            if (!form.contains(event.target)) {
                clearPanel();
            }
        });
    });
})();
