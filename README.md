# 🤖 Telegram Channel Bot

AI-бот для Telegram-канала с поддержкой Claude.

## Быстрый старт

```bash
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env
python bot.py
```

## Команды

| Команда | Описание |
|---------|----------|
| /start | Главное меню |
| /help | Справка |
| /clear | Сбросить диалог |
| /stats | Статистика (только admin) |
| /broadcast текст | Отправить в канал (только admin) |

## Деплой → Railway (бесплатно)

1. Залей на GitHub
2. Зайди на railway.app → New Project → Deploy from GitHub
3. Добавь переменные из .env в разделе Variables
4. Profit 🎉
