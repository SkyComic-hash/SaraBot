# SaraBot<div align="center">

# 🤖 SARA AI — Telegram Assistant & Code Auditor

**Мультифункциональный ассистент с искусственным интеллектом, памятью диалогов, модулем компьютерного зрения и анализом безопасности кода.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

</div>

---

## 🌟 Ключевые возможности

* 🧠 **Память и контекст диалога:** Бот запоминает историю сообщений в ЛС и групповых чатах благодаря встроенной базе данных SQLite (как в ChatGPT/Gemini).
* 🛡️ **Аудит безопасности кода:** Автоматический поиск уязвимостей, бэкдоров и потенциально опасных функций (`rm -rf`, `os.system`, слив токенов) при отправке файлов `.py`, `.sh`, `.cpp`, `.json` или блоков кода.
* 👁️ **Computer Vision:** Анализ скриншотов, схем и фото с помощью мультимодальных нейросетей (`ling-3.0-flash-vl`).
* 💬 **Умный групповой режим:** В группах бот не спамит на все сообщения, а откликается на имя **Сара / Sara**, прямые упоминания `@bot` или ответы (Reply).
* ⚡ **Inline Mode:** Возможность генерировать ответы AI прямо в тексте любого чата Telegram через команду `@username_bot запрос`.
* 💸 **Бесплатная инфраструктура:** Интеграция с роутером API (NaraRouter) и готовый деплой на PaaS (Koyeb / Render).

---

## 🏗️ Архитектура проекта

```text
sara-ai-bot/
├── bot.py             # Основной исполняемый файл бота (aiogram 3 + SQLite)
├── chat_history.db    # База данных SQLite (создается автоматически)
├── requirements.txt   # Зависимости проекта
├── Dockerfile         # Контейнеризация для Koyeb/Render
└── README.md          # Документация
