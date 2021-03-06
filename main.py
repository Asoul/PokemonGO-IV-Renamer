#!/usr/bin/env python
# coding=utf-8

"""This module renames Pokemon according to user configuration"""

import sys
import traceback
import json
import time
import argparse
from itertools import groupby
from datetime import datetime
from pgoapi import PGoApi
from pgoapi.exceptions import NotLoggedInException
from random import randint
from terminaltables import AsciiTable

class NoPokemoError(Exception):
    pass

class Renamer(object):
    """Main renamer class object"""

    def __init__(self):
        self.pokemon = []
        self.api = None
        self.config = None
        self.pokemon_list = None

    def init_config(self):
        """Gets configuration from command line arguments"""
        parser = argparse.ArgumentParser()

        parser.add_argument("-a", "--auth_service")
        parser.add_argument("-u", "--username")
        parser.add_argument("-p", "--password")
        parser.add_argument("-lo", "--list_only", action='store_true', default=False)
        parser.add_argument("--format", default="%ivsum, %atk/%def/%sta")
        parser.add_argument("-l", "--locale", default="en")
        parser.add_argument("--min_delay", type=int, default=10)
        parser.add_argument("--max_delay", type=int, default=20)
        parser.add_argument("--iv", type=int, default=0)

        self.config = parser.parse_args()

    def setup_api(self):
        """Prepare and sign in to API"""
        self.api = PGoApi()

        if not self.api.login(self.config.auth_service,
                              str(self.config.username),
                              str(self.config.password)):
            print("Login error")
            exit(0)

        print("Signed in")

    def get_pokemon(self):
        """Fetch Pokemon from server and store in array"""
        print("Getting Pokemon list")
        self.api.get_inventory()
        response_dict = self.api.call()

        self.pokemon = []
        try:
            inventory_items = response_dict['responses'] \
                                           ['GET_INVENTORY'] \
                                           ['inventory_delta'] \
                                           ['inventory_items']
        except KeyError:
            print("Get pokemo list error")
            if not response_dict.get('responses'):
                print('Error response_dict')
                print(response_dict)
            elif not response_dict.get('responses').get('GET_INVENTORY'):
                print('Error responses')
                print(response_dict.get('responses'))
            elif not response_dict.get('responses').get('GET_INVENTORY').get('inventory_delta'):
                print('Error GET_INVENTORY')
                print(response_dict.get('responses').get('GET_INVENTORY'))
            else:
                print("Error inventory_delta")
                print(response_dict.get('responses').get('GET_INVENTORY').get('inventory_delta'))
            raise NoPokemoError("Cannot get Pokemo")

        for item in inventory_items:
            try:
                item.get('inventory_item_data').get('pokemon_data')
            except KeyError:
                pass
            else:
                try:
                    pokemon = item['inventory_item_data']['pokemon_data']

                    pid = pokemon['id']
                    num = pokemon['pokemon_id']
                    name = self.pokemon_list[str(num)]

                    attack = pokemon.get('individual_attack', 0)
                    defense = pokemon.get('individual_defense', 0)
                    stamina = pokemon.get('individual_stamina', 0)
                    iv_percent = (float(attack + defense + stamina) / 45.0) * 100.0

                    nickname = pokemon.get('nickname', 'NONE')
                    combat_power = pokemon.get('cp', 0)

                    self.pokemon.append({
                        'id': pid,
                        'num': num,
                        'name': name,
                        'nickname': nickname,
                        'cp': combat_power,
                        'attack': attack,
                        'defense': defense,
                        'stamina': stamina,
                        'iv_percent': iv_percent,
                    })
                except KeyError:
                    pass
        # Sort the way the in-game `Number` option would, i.e. by Pokedex number
        # in ascending order and then by CP in descending order.
        self.pokemon.sort(key=lambda k: (k['num'], -k['cp']))

    def print_pokemon(self):
        """Print Pokemon and their stats"""
        sorted_mons = sorted(self.pokemon, key=lambda k: (k['num'], -k['iv_percent']))
        groups = groupby(sorted_mons, key=lambda k: k['num'])
        table_data = [
            ['Pokemon', 'CP', 'IV %', 'ATK', 'DEF', 'STA']
        ]
        for key, group in groups:
            group = list(group)
            pokemon_name = self.pokemon_list[str(key)].replace(u'\N{MALE SIGN}', '(M)').replace(u'\N{FEMALE SIGN}', '(F)')
            best_iv_pokemon = max(group, key=lambda k: k['iv_percent'])
            best_iv_pokemon['best_iv'] = True
            for pokemon in group:
                row_data = [
                    pokemon_name,
                    pokemon['cp'],
                    "{0:.0f}%".format(pokemon['iv_percent']),
                    pokemon['attack'],
                    pokemon['defense'],
                    pokemon['stamina']
                ]
                table_data.append(row_data)
        table = AsciiTable(table_data)
        table.justify_columns[0] = 'left'
        table.justify_columns[1] = 'right'
        table.justify_columns[2] = 'right'
        table.justify_columns[3] = 'right'
        table.justify_columns[4] = 'right'
        table.justify_columns[5] = 'right'
        print(table.table)

    def rename_pokemon(self):
        """Renames Pokemon according to configuration"""
        already_renamed = 0
        renamed = 0

        for pokemon in self.pokemon:
            individual_value = pokemon['attack'] + pokemon['defense'] + pokemon['stamina']
            iv_percent = int(pokemon['iv_percent'])

            if individual_value < 10:
                individual_value = "0" + str(individual_value)

            num = pokemon['num']
            pokemon_name = self.pokemon_list[str(num)]

            name = self.config.format
            name = name.replace("%id", str(num))
            name = name.replace("%ivsum", str(individual_value))
            name = name.replace("%atk", str(pokemon['attack']))
            name = name.replace("%def", str(pokemon['defense']))
            name = name.replace("%sta", str(pokemon['stamina']))
            name = name.replace("%percent", str(iv_percent))
            name = name.replace("%cp", str(pokemon['cp']))
            name = name.replace("%name", pokemon_name)
            name = name[:12]

            if (pokemon['nickname'] == "NONE" \
                or pokemon['nickname'] == pokemon_name \
                and iv_percent >= self.config.iv):

                self.api.nickname_pokemon(pokemon_id=pokemon['id'], nickname=name)
                response = self.api.call()

                try:
                    result = response['responses']['NICKNAME_POKEMON']['result']
                except KeyError:
                    print(response)
                    raise NoPokemoError("Cannot get Pokemo nickname after setting")

                if result == 1:
                    print("Renaming " + pokemon_name.replace(u'\N{MALE SIGN}', '(M)').replace(u'\N{FEMALE SIGN}', '(F)') + " (CP " + str(pokemon['cp'])  + ") to " + name)
                else:
                    print("Something went wrong with renaming " + pokemon_name.replace(u'\N{MALE SIGN}', '(M)').replace(u'\N{FEMALE SIGN}', '(F)') + " (CP " + str(pokemon['cp'])  + ") to " + name + ". Error code: " + str(result))

                random_delay = randint(self.config.min_delay, self.config.max_delay)
                time.sleep(random_delay)

                renamed += 1

            else:
                already_renamed += 1

        print(str(renamed) + " Pokemon renamed.")
        print(str(already_renamed) + " Pokemon already renamed.")

if __name__ == '__main__':
    renamer = Renamer()

    print("Start renamer")
    renamer.init_config()

    try:
        renamer.pokemon_list = json.load(open('locales/pokemon.' + renamer.config.locale + '.json'))
    except IOError:
        print("The selected language is currently not supported")
        exit(0)

    renamer.setup_api()

    while True:
        try:
            renamer.get_pokemon()
            # renamer.print_pokemon()
            renamer.rename_pokemon()
        except (NotLoggedInException, NoPokemoError):
            print("Not login, reset api")
            renamer.setup_api()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_strings = traceback.format_exception(exc_type, exc_value,
                                                       exc_traceback, limit=100)
            try:
                print('\n'.join(error_strings))
            except:
                pass

            sleep_time = 600 + randint(renamer.config.min_delay, renamer.config.max_delay)
            print('Unknown error occur, sleep additional {} seconds'.format(sleep_time))
            time.sleep(sleep_time)
        finally:
            timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            sleep_time = 60 + randint(renamer.config.min_delay, renamer.config.max_delay)
            print("[{}] Sleep {} sec to continue".format(timestamp, sleep_time))
            time.sleep(sleep_time)
