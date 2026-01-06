from multiprocessing import Process
import oms_chatbot_flask
import slack

if __name__ == "__main__":
    p1 = Process(target=slack.main)
    p2 = Process(target=oms_chatbot_flask.main)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
