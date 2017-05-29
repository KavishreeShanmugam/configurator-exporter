"""
Logger Plugin manager
"""
import copy
from config_util import *


class FluentdPluginManager:
    """
    Fluentd Plugin manager
    """

    def __init__(self, template_data):
        """
        Initialize member variables for Fluentd manager
        :param template_data:
        :return:
        """
        # Initialize defaults
        self.plugin_path = os.path.sep + 'etc' + os.path.sep + 'td-agent'
        self.service_name = 'td-agent'

        self.tags, self.plugins, self.target = [], [], []
        self.enable = template_data[ENABLED]
        self.tags = template_data.get(TAGS, [])
        self.logger_user_input = template_data

        self.plugin_config = read_yaml_file(FluentdPluginMappingFilePath)
        self.target_mapping_list = get_supported_targets_mapping()

        self.plugin_post_data, self.status = [], []

        # Initialize logger object
        self.logger = expoter_logging(COLLECTD_MGR)
        self.logger.info('Logger Object Successfully Initialized.')
        # self.logger.info('Targets Nodes : %s', str(self.nodelist))
        self.logger.info('User Input : %s', str(self.logger_user_input))

    def start(self):
        """
        Start call for td-agent service
        """
        self.logger.debug('Server - td-agent - start call.')
        self.change_service_status("start")

    def restart(self):
        """
        Restart call for td-agent service
        """
        self.logger.debug('Server - td-agent - restart call.')
        self.change_service_status("restart")

    def stop(self):
        """
        Stop call for td-agent service
        """
        self.logger.debug('Server - td-agent - stop call.')
        self.change_service_status("stop")

    # def teardown(self):
    #     """
    #     Teardown call for td-agent service
    #     """
    #     self.logger.debug('Server - td-agent - Teardown call.')
    #     self.change_service_status("stop")
    #
    #     # Clear the indexes from template created by input template.
    #     for target_details in self.logger_user_input.get(TARGETS, []):
    #         if target_details.get('type') == "elasticsearch":
    #             es_details = target_details
    #             es_conn = Elasticsearch([{'host': es_details.get(HOST),
    #                                       'port': int(es_details.get(PORT))}], verify_certs=True)
    #             status = es_conn.indices.delete(
    #                 index=es_details.get('index'), ignore=[400, 404])
    #             if status.get('acknowledged'):
    #                 self.logger.debug(
    #                     '%s: Index successfully Deleted.', es_details.get('index'))
    #             else:
    #                 self.logger.debug('Error: %s: %s', es_details.get('index'),
    #                                   status.get('error').get('reason'))
    #         else:
    #             self.logger.error(
    #                 'Target is not elastic search database(Yet to handle).')
    #     self.logger.info('Logger Teardown Complete.')

    def check_status(self):
        """
        Check status call for td-agent service
        """
        self.logger.debug('Server - td-agent - check_status call.')
        self.change_service_status("status")
        return self.status

    def change_service_status(self, operation):
        """
        Change service status call as per operation param passed
        :param operation: start/stop/status/restart
        :return: status message as per operation passed.
        """
        try:
            pass
        except Exception as err:
            self.logger.debug("Exception: %s ", str(err))

    def configure_plugin_data(self):
        """
        Generate plugin data based on template data as dictionary
        """
        # Read template config, merge them with plugin config and generate
        # plugin params
        self.logger.info('Configuring the plugin data.')
        for x_plugin in self.logger_user_input.get('plugins'):
            temp = dict()
            temp['source'] = {}
            temp['source']['tag'] = x_plugin.get('tags', [])
            temp['name'] = x_plugin.get(NAME)

            if x_plugin.get(NAME) in self.plugin_config.keys():
                plugin = self.plugin_config.get(
                    x_plugin.get(NAME))
                temp['source'].update(plugin.get('source'))
                temp['filter'] = plugin.get('filter')
                temp['match'] = plugin.get('match')
            else:
                strr = 'In-Valid input plugin type.' + x_plugin.get(NAME)
                self.logger.warning(strr)
                temp[STATUS] = "FAILED: Unsupported logging Plugin"
                self.plugins.append(temp)
                continue

            filter_lower = [x.lower()
                            for x in x_plugin.get('filter', [])]
            filter_upper = [x.upper()
                            for x in x_plugin.get('filter', [])]

            if 'WARNING' in filter_upper:
                filter_upper.remove('WARNING')
                filter_upper.append('WARN')

            if 'all' in filter_lower:
                if x_plugin.get(NAME) == 'syslog':
                    temp['source']['log_level'] = 'debug'
                else:
                    if not temp['source'].get('format'):
                        temp['source']['format'] = 'none'
                    # temp['source']['format'] = 'none'
                    temp['usr_filter'] = '(.*?)'
            else:
                if x_plugin.get(NAME) == 'syslog':
                    temp['source']['log_level'] = filter_upper[0].lower()
                else:
                    if not temp['source'].get('format'):
                        temp['source']['format'] = 'none'
                    # temp['source']['format'] = 'none'
                    temp[
                        'usr_filter'] = '(.*(' + '|'.join(filter_upper) + ').*?)'

            self.plugins.append(temp)
        self.logger.info('Plugin data successfully Configured.')
        return True

    def configure_plugin_file(self, data):
        """
        Push configured plugin data to file
        :param data: Generate plugin data based on param passed and push config to file
        :return: True if operation is successful
        """
        # Add source.
        source_tag = str()
        lines = ['<source>']
        for key, val in data.get('source', {}).iteritems():
            if isinstance(val, list):
                try:
                    source_tag = val[0] + '.*'
                except Exception as err:
                    self.logger.debug('Plugin tags not configured. Using plugin name as tag.'
                                      'Exception - %s ', str(err))
                    source_tag = data.get('name') + '.*'
                    lines.append('\t' + key + ' ' + source_tag)
                    continue
                '''
                source_tag = val[0]
                except:
                    self.logger.debug('Plugin tags not configured. Using plugin name as tag.')
                    source_tag = data.get('name')
                '''
                lines.append('\t' + key + ' ' + source_tag)
                continue
            lines.append('\t' + str(key) + ' ' + str(val))

        lines.append('</source>')
        # Add grep filter.
        if data.get('usr_filter', None):
            lines.append('\n<filter ' + source_tag + '*>')
            lines.append('\t@type grep')
            lines.append('\tregexp1 message ' + data.get('usr_filter'))
            lines.append('</filter>')

        # Add record-transormation filter. if data.get('match').has_key('tag'):
        if 'tag' in data.get('match'):
            lines.append('\n<filter ' + source_tag + '.' +
                         data.get('match').get('tag', []) + '>')
        else:
            lines.append('\n<filter ' + source_tag + '*>')
        lines.extend(['\t@type record_transformer', '\t<record>'])
        for key, val in data.get('filter', {}).iteritems():
            lines.append('\t\t' + key + ' \"' + val + '\"')

        # lines.append('\t\ttags ' + str(self.tags + [data.get('source').get('tag')]))
        tags = [str(x) for x in self.tags + data.get('source').get('tag')]
        lines.append('\t\ttags ' + str(tags).replace('\'', '"'))
        lines.extend(['\t</record>', '</filter>'])

        # Add match. if data.get('match').has_key('tag'):
        for x_targets in self.logger_user_input.get('targets'):
            if STATUS not in x_targets:
                if 'tag' in data.get('match'):
                    lines.append('\n<match ' + source_tag + '.' +
                                 data.get('match').get('tag') + '>')
                    data.get('match').pop('tag')
                else:
                    lines.append('\n<match ' + source_tag + '*>')

                for key, val in x_targets.iteritems():
                    if key == "type":
                        key = "@" + key
                    if key == "index":
                        key += "_name"
                    if key == "enable":
                        continue
                    lines.append('\t' + key + ' ' + val)

                for key, val in data.get('match', {}).iteritems():
                    lines.append('\t' + str(key) + ' ' + str(val))
                lines.append('</match>')

        filename = self.plugin_path + os.path.sep + data.get('name')
        self.plugin_post_data.append((filename, '\n'.join(lines)))
        return True

    def generate_plugins(self):
        """
        Generate plugin data
        :return: true if operation is successful
        """
        # Generate the files in the salt dir
        self.configure_plugin_data()

        for x_plugin in self.plugins:
            if STATUS not in x_plugin:
                self.logger.debug('Configuring the plugin: %s', (str(x_plugin)))
                self.configure_plugin_file(x_plugin)
        return True

    def generate_fluentd_config_file(self):
        """
        Generate fluentd config file
        :return: True if operation is successful
        """
        self.logger.info('Generating fluentd config file (td-agent.conf).')
        lines = []
        for x_plugin in self.plugins:
            if STATUS not in x_plugin:
                lines.append('@include ' + x_plugin.get('name'))

        for x_targets in self.logger_user_input.get('targets'):
            if STATUS not in x_targets:
                lines.append('\n<match *>')
                # for key, val in self.logger_user_input.get('targets')[0].iteritems():
                for key, val in x_targets.iteritems():
                    if key == "type":
                        key = "@" + key
                    if key == "index":
                        key += "_name"
                    if key == "enable":
                        continue
                    lines.append('\t' + key + ' ' + val)

                lines.append('\t' + 'flush_interval' + ' ' +
                             str(self.plugin_config.get('default_flush_interval', '120s')))
                lines.append('\t' + 'include_tag_key' + ' true')
                lines.append('</match>')

        filename = self.plugin_path + os.path.sep + 'td-agent.conf'
        self.plugin_post_data.append((filename, '\n'.join(lines)))
        return True

    # def deploy(self, oper):
    #     """
    #     Deploy logger based on operation
    #     :param oper: start/stop
    #     :return:
    #     """
    #     self.logger.info('Deployment Started.')
    #     self.logger.debug('Operation : ' + str(oper))
    #     self.logger.debug(
    #         'Enable : ' + str(self.logger_user_input.get('enable', False)))
    #
    #     salt_obj = SaltManager()
    #     # status = {}
    #     if oper == START:
    #         if self.logger_user_input.get('enable', False):
    #             self.generate_plugins()
    #             self.generate_fluentd_config_file()
    #             # print '\nPost Data: ', json.dumps(self.plugin_post_data)
    #
    #             self.logger.info('Pushing the configs to the target node.')
    #             self.logger.debug('self.plugin_post_data' +
    #                               json.dumps(self.plugin_post_data))
    #             status = salt_obj.push_config(
    #                 self.plugin_post_data, self.nodelist)
    #             self.logger.debug('Push Status :' + json.dumps(status))
    #             self.restart()
    #         else:
    #             self.stop()
    #     elif oper == STOP:
    #         if self.logger_user_input.get('enable', False):
    #             disable_files, disable_plugins = [], []
    #             for x_plugin in self.logger_user_input.get('plugins'):
    #                 disable_plugins.append(x_plugin.get('type'))
    #                 disable_files.append(
    #                     self.plugin_path + os.path.sep + x_plugin.get('type'))
    #
    #             self.logger.info(
    #                 'Plugin disable in progress : ' + str(disable_plugins))
    #             status = salt_obj.delete_files(disable_files, self.nodelist)
    #             new_config_data = salt_obj.reset_logger_config(
    #                 disable_plugins, self.nodelist)
    #             config_post_data = [[self.plugin_path + os.path.sep +
    #                                  'td-agent.conf', new_config_data]]
    #             self.logger.debug('self.plugin_post_data' +
    #                               json.dumps(config_post_data))
    #             config_status = salt_obj.push_config(
    #                 config_post_data, self.nodelist)
    #             self.logger.debug('Config Push Status :' +
    #                               json.dumps(config_status))
    #             status.update(config_status)
    #             self.restart()
    #         else:
    #             self.stop()
    #
    #     elif oper == 'teardown':
    #         self.logger.info('Teardown Started.')
    #         self.stop()
    #         return
    #
    #     else:
    #         pass
    #
    #     self.change_service_status("status")
    #     return self.status

    def create_conf_files(self):
        for cnf in self.plugin_post_data:
            file_writer(cnf[0], cnf[1])

    def bulid_set_config_result(self):
        logging = {}

        for x_plugin in self.plugins:
            if STATUS not in x_plugin:
                x_plugin[STATUS] = "SUCCESS: Plugin configured"

        logging[PLUGINS] = self.plugins

        for x_targets in self.logger_user_input.get(TARGETS):
            if STATUS not in x_targets:
                x_targets[STATUS] = "SUCCESS: targets configured"

        logging[TARGETS] = self.logger_user_input.get(TARGETS)

        return logging

    def store_set_config(self):
        """

        :return:
        """
        error_msg = ""
        logging = {}
        plugins_list = copy.deepcopy(self.plugins)
        targets_list = copy.deepcopy(self.logger_user_input.get(TARGETS))
        try:
            # Build plugin Result
            for i in range(len(plugins_list)):
                if STATUS in plugins_list[i] and "FAILED" in plugins_list[i][STATUS]:
                    del plugins_list[i]
                    continue

                if STATUS in plugins_list[i]:
                    del plugins_list[i][STATUS]

            logging[PLUGINS] = plugins_list

            for i in range(len(targets_list)):
                if STATUS in targets_list[i] and "FAILED" in targets_list[i][STATUS]:
                    del targets_list[i]
                    continue

                if STATUS in targets_list[i]:
                    del targets_list[i][STATUS]

            logging[TARGETS] = targets_list

            # Store config data
            file_writer(FluentdData, json.dumps(logging))
            self.logger.info(" maintain set configuration data for configurator to use")

        except Exception as e:
            error_msg += "Logging configutration storing failed: "
            error_msg += str(e)
            self.logger.error(error_msg)

    def verify_targets(self):
        print self.target_mapping_list
        for x_targets in self.logger_user_input.get('targets'):
            if x_targets[TYPE] in self.target_mapping_list.keys():
                pass
            else:
                x_targets[STATUS] = "FAILED: Unsupported metrics targets"

    def set_config(self):
        """
        configure fluentd
        :return:
        """
        return_dict = {}
        error_msg = ""
        try:
            self.logger.info('Deployment Started.')
            self.logger.debug(
                'Enable : ' + str(self.enable))

            success, error_msg = delete_fluentd_config()
            self.verify_targets()
            self.generate_plugins()
            self.generate_fluentd_config_file()

            self.logger.info('Pushing the configs to the target node.')
            self.logger.debug('self.plugin_post_data' +
                              json.dumps(self.plugin_post_data))
            self.create_conf_files()
            if self.enable:
                # self.restart()
                change_fluentd_status(RESTART)
            else:
                # self.stop()
                change_fluentd_status(STOP)

            return_dict = self.bulid_set_config_result()
            self.logger.info("Bulid set configuration result completed")

            # Stored copnfiguration locally.
            self.store_set_config()

        except Exception as e:
            error_msg += str(e)
            return_dict[ERROR] = error_msg
            self.logger.error("Set fluentd config failed")
            self.logger.error(str(e))

        return return_dict