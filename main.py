from backend import keep_alive
import telebot
from settings import TG_TOKEN
import pendulum
import sqlite3
import requests
import numpy as np
import pickle
from matplotlib import pyplot as plt

bot = telebot.TeleBot(TG_TOKEN)
with open('files/USD_RUB_model.pkl', 'rb') as file:
    model = pickle.load(file)
file.close()


def create_graph():
    now = pendulum.now('UTC').format('YYYY-MM-DD')

    con = sqlite3.connect('data.db')
    print(con)
    cur = con.cursor()
    print(cur)

    cur.execute(""" SELECT MAX(days) FROM USD_RUB_data""")
    row = cur.fetchall()
    db_date = row[0][0]

    print('дата сейчас -', now)
    print('дата из БД  -', db_date)
    if now >= db_date:
        print('Обновление БД')
        # открываем данные для нормализации
        m_m_open = open('files/min_max.txt', 'r')
        val = m_m_open.read()
        m_m_open.close()
        min_max_lst = list(map(float, val.split()))

        # получаем данные с API
        url = 'https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=RUB&apikey=W284OCJ6Y1UZJK7P'
        r = requests.get(url)
        data = r.json()

        counter = 0
        for i in data['Time Series FX (Daily)'].items():
            done = True
            d = dict(i[1])
            lst = []
            if db_date > now:
                break
            for j in d.items():
                lst.append(float(j[1]))
            # Нормализация
            lst_norm = [(x - min_max_lst[0]) / (min_max_lst[1] - min_max_lst[0]) for x in lst]

            days = i[0]
            # если даты нет в базе продолжаем
            if days == db_date:
                done = False
            opening, high, low, closes = tuple(lst_norm)
            close_c = lst[3]
            X = np.array(lst_norm).reshape(1, -1)
            # Создание предсказания
            predict_after = model.predict(X)

            if counter > 0:
                predict = round(float(predict_before), 2)
            else:
                cur.execute(f""" SELECT predict FROM USD_RUB_data WHERE days = '{db_date}'""")
                pred = cur.fetchall()
                predict = pred[0][0]

            if not done:
                try:

                    cur.execute(
                        f"""INSERT INTO USD_RUB_data VALUES('{days}', {opening}, {high}, {low}, {closes}, {close_c}, {predict}) """)
                except sqlite3.IntegrityError:
                    print('дата уже существует')

            if days == db_date:
                print('обновляю текщую дату')
                cur.execute(
                    f"""UPDATE USD_RUB_data SET opening = {opening}, high = {high}, low = {low},
                     closes = {closes}, close_c =  {close_c}, predict = {predict} WHERE days ='{days}' """)

            predict_before = predict_after
            print(days)
            if not done:
                break
            counter += 1

        days = pendulum.tomorrow('UTC').format('YYYY-MM-DD')
        print('создаю predict на завтра')
        cur.execute(f"""INSERT INTO USD_RUB_data (days, predict) VALUES('{days}',{round(float(predict_after), 2)}) """)

        # Получаем данные для графика
        cur.execute("""SELECT close_c, predict, days FROM USD_RUB_data ORDER BY days""")
        close_pred = cur.fetchall()
        days = []
        real = []
        pre = []
        for i in close_pred:
            if i[0] is not None:
                real.append(i[0])
            pre.append(i[1])
            days.append(i[2])


        # строим график и сохраняем.

        plt.plot(days[-100:-1], real[-99:], label='Real USD/RUB exchange rate')
        plt.plot(days[-100:], pre[-100:], label=f'Predicted USD/RUB exchange rate\nForecasted closing rate : {pre[-1]}')
        plt.legend()
        plt.grid()
        plt.xticks(color='w')
        plt.xlabel('Date')
        plt.ylabel('Exchange')
        plt.title('Prediction of dynamics on ' + days[-1])
        plt.savefig('img_pred/predict_show.jpg')
        # ???предупреждение о разных потоках и глючности матплот
    #con.commit()

    cur.close()

#create_graph()
@bot.message_handler(content_types=['text'])
def get_text_message(message):
    bot.send_message(message.from_user.id, "Для получения графика введите - pred")

    if message.text == 'pred':
        create_graph()
        with open('img_pred/predict_show.jpg', 'rb') as fil:
            byte = fil.read()
        print('отправлено')

        bot.send_photo(message.from_user.id, byte)

# заглушка для работоспособности на replite
keep_alive()
bot.infinity_polling()
