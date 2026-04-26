poker-bot/
  app/
    main.py

    config/
      settings.py
      logging.py

    api/
      http/
        health.py
        telegram_webhook.py
        vk_webhook.py

    bot/
      shared/
        texts/
          user.py
          admin.py
        buttons/
          common.py
        states/
          user.py
          admin.py
        navigation/
          pagination.py

      telegram/
        handlers/
          user.py
          admin.py
          poker.py
          betting.py
        renderer.py
        adapter.py

      vk/
        handlers/
          user.py
          admin.py
          poker.py
          betting.py
        renderer.py
        adapter.py

    application/
      dto/
        user.py
        poker.py
        betting.py
        stats.py

      use_cases/
        registration/
          start_registration.py
          approve_registration.py

        poker/
          create_game.py
          start_game.py
          finish_game.py
          show_current_game.py

        buyins/
          add_buyin.py
          rebuy.py
          cashout.py
          list_buyins.py

        betting/
          create_bet.py
          settle_bet.py
          cancel_bet.py
          list_bets.py

        stats/
          player_stats.py
          game_stats.py
          buyin_chart.py

    domain/
      models/
        user.py
        poker_game.py
        player_in_game.py
        buyin.py
        bet.py

      services/
        registration_service.py
        poker_service.py
        buyin_service.py
        betting_service.py
        stats_service.py

      rules/
        access.py
        validators.py
        calculations.py

    infrastructure/
      db/
        base.py
        models/
          user.py
          poker_game.py
          buyin.py
          bet.py
        repositories/
          user_repository.py
          poker_repository.py
          buyin_repository.py
          bet_repository.py

      integrations/
        telegram/
        vk/

      charts/
        buyin_chart_builder.py

    core/
      enums.py
      exceptions.py
      dependencies.py

    utils/
      dates.py
      strings.py
      regex.py

  alembic/
    versions/

  tests/
    application/
    domain/
    api/

  .env
  .env.example
  alembic.ini
  pyproject.toml
  README.md
Как мыслить по слоям:

api/http — webhook endpoints.
bot/telegram и bot/vk — только платформенная обвязка.
application/use_cases — реальные сценарии, которые вызывают обе платформы.
domain — бизнес-логика покера, ставок, закупов, расчётов.
infrastructure/db — SQLAlchemy модели, репозитории и SQLite.
infrastructure/charts — генерация графиков в файл/bytes.