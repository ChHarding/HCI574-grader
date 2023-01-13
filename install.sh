#!/bin/bash

#known bugs
#does note remove old aliases from .zshrc and .bash_profile

#install virtual envrionment
pip install --user virtualenv

#setup canvas token
nbcanrc_file=~/.nbcanrc
reconf="true"

if [ -f $nbcanrc_file ]; then
  while true; do
    echo -e "\n"
    clear
    read -p "Previous canvas token found. Reconfigure? This will overwrite the old token? (yes/no) " yn
    case $yn in
        [Yy]* ) printf "configuring...\n"; break;;
        [Nn]* ) printf "skipping...\n"; reconf="false"; break;;
        * ) echo "Please answer yes or no.";;
    esac
  done
fi

if [ $reconf == "true" ] ; then
  #get canvas authentication info
  #echo -e "\n\n\n\n"
  printf "Removing old file ($nbcanrc_file)"
  rm -f $nbcanrc_file
  clear
  read -p "Enter the Canvas authentication token (see setup files for more info): " canvas_token
  echo -e ""
  read -p "Enter Canvas course-id (see setup files for more info): " course_id
  root_dir=`pwd`
  #write date to nbcanrc file
  clear    
  printf "Writing canvas token to: $nbcanrc_file\n\n  Note: change the $nbcanrc_file file if all directories are not all in the project root folder ($root_dir)\n"
  echo -e "[canvas]" >> $nbcanrc_file
  echo -e "access-token=$canvas_token" >> $nbcanrc_file
  echo -e "root-url=https://canvas.iastate.edu/" >> $nbcanrc_file
  echo -e "course-id=$course_id" >> $nbcanrc_file
  echo -e "" >> $nbcanrc_file
  echo -e "[nbgrader]" >> $nbcanrc_file
  echo -e "root-dir=$root_dir" >> $nbcanrc_file
  echo -e "% exchange-dir=/Users/<your-username>/Projects/574/HCI574_<course-year>>_HW/exchange/  % if dirs are not all in proj. root" >> $nbcanrc_file
  echo -e "course-name=HCI574" >> $nbcanrc_file

  printf "\nDone Reconfiguring\n\n"
fi



#setup virtual envrionment directory
venv_dir=~/hci574_env
if [ -d $venv_dir ]
then
  #ask user to reinstall tools if previous envrionment is found
  while true; do
    read -p "Previous environment installed. Reinstall? (yes/no) " yn
    case $yn in
        [Yy]* ) printf "reinstalling...\n"; break;;
        [Nn]* ) printf "exiting...\n"; exit;;
        * ) echo "Please answer yes or no.";;
    esac
  done
else
  printf "installing..."
fi

#remove old virtual envrionment folder (if exists) and create a new one
rm -rf $venv_dir
python3 -m venv $venv_dir 

printf "created environment\n"

#activate virtual environment
printf "activating virtual environment"
source $venv_dir/bin/activate


printf "installing dependencies"
pip3 install -r requirements.txt

jupyter nbextension install --user --py nbgrader --overwrite
jupyter nbextension enable --user --py nbgrader
jupyter serverextension enable --user --py nbgrader

#Configure Student List
printf "\nConfiguring Student List\n"
cd nbgrader_canvas_tool/
python3 nbgrader_canvas_tool.py export-student-list /tmp/student_list.csv
nbgrader db student import /tmp/student_list.csv
rm /tmp/student_list.csv
cd ..


#deactivating envrionment and ending install
deactivate

#install aliases for zsh and bash
bash_config=~/.bash_profile
zsh_config=~/.zshrc
hci574_hw_dir=`pwd`
alias_name="start_grading"

#config zsh
if [ -f $zsh_config ]; then
  touch $zsh_config
fi

#append when file exists
echo -e "\n#alias for starting the hci574 grading environment" >> $zsh_config
echo "alias $alias_name=\"source $venv_dir/bin/activate; cd $hci574_hw_dir; jupyter notebook; deactivate\" " >>$zsh_config


#config bash
if [ -f $bash_config ]; then
  touch $bash_config
fi

#append when file exists
echo -e "\n#alias for starting the hci574 grading environment" >> $bash_config
echo "alias $alias_name=\"source $venv_dir/bin/activate; cd $hci574_hw_dir; jupyter notebook; deactivate\" " >>$bash_config



printf "\n\n\nDone Installing\n"

#configure command to allow alias to be run
reload_config_script=./reload_config.sh
if [ $SHELL "==" '/bin/bash' ] ; then
  echo -e "source $bash_config" > $reload_config_script
  echo -e "rm -f $reload_config_script" >> $reload_config_script
  
elif [ $SHELL "==" '/bin/zsh' ] ; then
  echo -e "source $zsh_config" > $reload_config_script
  echo -e "rm -f $reload_config_script" >> $reload_config_script
else
  echo "WARNING: unsupported default shell. Please use \"bash $alias_name\" or \"zsh $alias_name\" to grade"
  exit
fi

#save command to run to file for easy shell reloading
cmd_to_run="source $reload_config_script"


printf "\n\nNOTE: for the changes to take effect either\n\n 1) restart your terminal \n     or\n 2) run \'$cmd_to_run\'\n\n\n"
