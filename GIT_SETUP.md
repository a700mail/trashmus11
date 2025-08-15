# Настройка Git репозитория

## 1. Создайте репозиторий на GitHub

1. Перейдите на https://github.com
2. Нажмите "New repository"
3. Назовите репозиторий (например: `telegram-music-bot`)
4. Сделайте его публичным или приватным
5. НЕ инициализируйте с README, .gitignore или license

## 2. Подключите удаленный репозиторий

После создания репозитория выполните команды:

```bash
# Добавьте удаленный репозиторий (замените YOUR_USERNAME и REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Переименуйте основную ветку в main (современный стандарт)
git branch -M main

# Отправьте код в репозиторий
git push -u origin main
```

## 3. Проверьте подключение

```bash
git remote -v
```

## 4. Дальнейшие изменения

```bash
git add .
git commit -m "Описание изменений"
git push
```

## 5. Деплой на Render

После настройки Git:
1. Перейдите на https://render.com
2. Создайте новый Web Service
3. Подключите ваш GitHub репозиторий
4. Настройте переменные окружения
5. Деплой запустится автоматически
