import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.info('Начала отправки сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    logger.info('Начало запроса к API')
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException:
        raise Exception
    if homework_statuses.status_code != HTTPStatus.OK:
        raise Exception(
            f'Запрос не успешный. '
            f'Код ответа {homework_statuses.status_code} отличный от 200'
        )

    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответствие документации. Не словарь')
    if 'homeworks' not in response.keys():
        raise Exception('Ответ API не соответствие документации. '
                        'Отсутствует ключ "homeworks"')
    if 'current_date' not in response.keys():
        raise Exception('Ответ API не соответствие документации. '
                        'Отсутствует ключ "current_date"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не соответствие документации. '
                        'homeworks не список')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API домашки нет ключа "homework_name".')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('В ответе API домашки нет ключа "status".')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'В словаре {HOMEWORK_VERDICTS} '
                       f'нет ключа {homework_status}.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    last_message = ''

    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения '
                        'во время запуска бота')
        sys.exit('Переменная не определена')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())     # для тестирования 1678884576

    while True:

        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')

            # if len(check_response(response)) == 0:

            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if last_message != message:
                    send_message(bot, message)
                    last_message = message
            else:
                logger.debug('Не появился новый статус — список работ пуст')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_message != message:
                send_message(bot, message)
                last_message = message
            else:
                logger.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
