/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.BravicoChat = publicWidget.Widget.extend({
    selector: ".js-bravico-chat",
    events: {
        "submit .js-bravico-chat-form": "_onSubmit",
        "click .js-bravico-suggestion": "_onSuggestion",
    },

    start() {
        this._busy = false;
        this._scrollToLatest();
        return this._super(...arguments);
    },

    _messageElement(role, content, sources = [], typing = false) {
        const row = document.createElement("div");
        row.className = `bravico-message-row bravico-message-${role} bravico-message-enter`;
        if (typing) {
            row.classList.add("bravico-message-pending");
        }

        if (role === "assistant") {
            const avatar = document.createElement("img");
            avatar.className = "bravico-assistant-avatar";
            avatar.src = "/portail_rh/static/src/img/bravico-square.png";
            avatar.alt = "Bravi";
            row.appendChild(avatar);
        }

        const bubble = document.createElement("div");
        bubble.className = "bravico-message-bubble";
        const author = document.createElement("div");
        author.className = "small fw-bold mb-1";
        author.textContent = role === "user" ? "Vous" : "Bravi";
        bubble.appendChild(author);

        const message = document.createElement("div");
        message.className = typing ? "bravico-typing" : "bravico-message-content";
        if (typing) {
            message.setAttribute("role", "status");
            message.setAttribute("aria-label", "Bravi prépare sa réponse");
            const accessibleLabel = document.createElement("span");
            accessibleLabel.className = "visually-hidden";
            accessibleLabel.textContent = "Bravi prépare sa réponse";
            message.appendChild(accessibleLabel);
            const dots = document.createElement("span");
            dots.className = "bravico-typing-dots";
            dots.setAttribute("aria-hidden", "true");
            for (let index = 0; index < 3; index++) {
                dots.appendChild(document.createElement("span"));
            }
            message.appendChild(dots);
        } else {
            message.textContent = content;
        }
        bubble.appendChild(message);

        if (sources.length) {
            const sourceBox = document.createElement("div");
            sourceBox.className = "mt-3 pt-3 border-top";
            const title = document.createElement("strong");
            title.className = "small";
            title.textContent = "Sources";
            sourceBox.appendChild(title);
            const list = document.createElement("ol");
            list.className = "small mb-0 mt-1";
            for (const source of sources) {
                const item = document.createElement("li");
                const score = Math.round(Number(source.score || 0) * 100);
                item.textContent = `${source.title} — ${source.section} (${score}%)`;
                list.appendChild(item);
            }
            sourceBox.appendChild(list);
            bubble.appendChild(sourceBox);
        }
        row.appendChild(bubble);
        return row;
    },

    _messagesContainer() {
        return this.el.querySelector(".js-bravico-chat-messages");
    },

    _scrollToLatest() {
        const container = this._messagesContainer();
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    },

    _onSuggestion(event) {
        const form = this.el.querySelector(".js-bravico-chat-form");
        const input = form && form.querySelector("[name='question']");
        if (!form || !input || this._busy) {
            return;
        }
        input.value = event.currentTarget.dataset.question || "";
        form.requestSubmit();
    },

    async _onSubmit(event) {
        event.preventDefault();
        if (this._busy) {
            return;
        }
        const form = event.currentTarget;
        const input = form.querySelector("[name='question']");
        const question = (input && input.value || "").trim();
        if (question.length < 2 || question.length > 2000) {
            input && input.reportValidity();
            return;
        }

        const container = this._messagesContainer();
        if (!container) {
            form.submit();
            return;
        }
        container.classList.remove("d-none");
        const submitButton = form.querySelector("button[type='submit']");
        const idleLabel = submitButton && (submitButton.dataset.idleLabel || submitButton.textContent.trim());
        this._busy = true;
        form.setAttribute("aria-busy", "true");
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.classList.add("is-loading");
            submitButton.setAttribute("aria-label", "Bravi prépare sa réponse");
        }

        container.appendChild(this._messageElement("user", question));
        const typingMessage = this._messageElement("assistant", "", [], true);
        container.appendChild(typingMessage);
        this._scrollToLatest();

        try {
            const response = await fetch(form.dataset.endpoint || "/my/onboarding/ask_json", {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || "Impossible d'envoyer le message.");
            }
            typingMessage.replaceWith(
                this._messageElement("assistant", payload.answer, payload.sources || [])
            );
            input.value = "";
        } catch (error) {
            typingMessage.replaceWith(
                this._messageElement(
                    "assistant",
                    error.message || "Le service est momentanément indisponible. Réessayez.",
                )
            );
        } finally {
            this._busy = false;
            form.removeAttribute("aria-busy");
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.classList.remove("is-loading");
                submitButton.removeAttribute("aria-label");
                submitButton.textContent = idleLabel;
            }
            this._scrollToLatest();
            input && input.focus();
        }
    },
});
