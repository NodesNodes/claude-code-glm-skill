# Claude Code → GLM Coding Plan

Скил для переключения Claude Code на GLM по подписке **Z.ai Coding Plan**. Основан на проверенной конфигурации Claude Code 2.1.314: GLM-5.3, контекст 1M и GLM-5.3-Flash для отдельных проверок auto mode.

## Установка скила в Claude Code

```bash
git clone https://github.com/NodesNodes/claude-code-glm-skill.git ~/.claude/skills/claude-code-glm-skill
```

В Claude Code вызови `/claude-code-glm-skill` и попроси переключить модель. Полный порядок действий находится в [SKILL.md](SKILL.md).

## Использование скрипта вручную

Требуются Python 3.8+ и установленный Claude Code. Получи ключ в своём **Z.ai Coding Plan → Plan Overview**. Подписка Claude Pro/Max не предоставляет доступ к GLM. Подписка Coding Plan использует ключ для доступа к своей квоте; это отличается от обычного API с оплатой по токенам.

Перейди в каталог скила и запусти:

```bash
python3 scripts/configure_glm.py configure
```

Скрипт запросит ключ скрытым вводом, если подходящего ключа ещё нет в настройках или переменной `ZAI_CODING_PLAN_API_KEY`. Также можно передать путь к файлу с ключом:

```bash
python3 scripts/configure_glm.py configure --key-file /absolute/path/to/coding-plan.key
```

Ключ хранится в пользовательских настройках Claude Code. Скрипт создаёт файл и копии с доступом только владельцу на POSIX, сохраняет остальные поля и не выводит секрет. Конфигурацию другого пользователя можно указать глобальным аргументом перед командой:

```bash
python3 scripts/configure_glm.py --settings /absolute/path/to/settings.json status
```

После настройки перезапусти Claude Code. Для продолжения сессии из её исходного рабочего каталога:

```bash
claude --continue
```

## Если auto mode долго ждёт

Для Claude Code 2.1.302+:

```bash
python3 scripts/configure_glm.py configure --client-auto
```

Это оставляет проверки разрешений включёнными и выполняет их отдельными запросами через GLM Flash. Флаг не включает auto mode сам по себе и не предоставляет дополнительные разрешения. Такие запросы могут расходовать квоту Coding Plan. Уведомление о бесплатных серверных проверках Anthropic связано с совместимостью провайдера; успешность подписки по нему не определяется.

## Проверка и откат

```bash
python3 scripts/configure_glm.py status
python3 scripts/configure_glm.py restore --backup /absolute/path/to/settings.before-glm.TIMESTAMP.json
```

Путь к резервной копии печатается при настройке. Откат восстанавливает полный снимок настроек, предварительно сохранив текущий файл. Изменения, сделанные после создания выбранной копии, тоже откатятся.

После переключения проверь не только ответ модели, но и выполнение простой команды Bash. Конкретные проверки и разбор предупреждений приведены в [скиле](SKILL.md#проверка).

Личные ключи, настройки и копии должны оставаться за пределами репозитория. Скрипт не переносит вход ZCode OAuth в Claude Code: нужен ключ Coding Plan.

## Источники

- [Z.ai — Claude Code](https://docs.z.ai/devpack/tool/claude)
- [Z.ai — Coding Plan](https://docs.z.ai/devpack/overview)
- [Claude Code — конфигурация моделей](https://code.claude.com/docs/en/model-config)
- [Claude Code — auto mode](https://code.claude.com/docs/en/permission-modes#server-side-classifier-review)
