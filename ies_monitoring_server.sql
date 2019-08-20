-- phpMyAdmin SQL Dump
-- version 4.5.4.1deb2ubuntu2.1
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Jun 28, 2019 at 04:48 PM
-- Server version: 5.7.26-0ubuntu0.16.04.1
-- PHP Version: 5.6.40-8+ubuntu16.04.1+deb.sury.org+1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `ies_monitoring_server`
--

-- --------------------------------------------------------

--
-- Table structure for table `messages`
--

CREATE TABLE `messages` (
  `id` int(11) NOT NULL COMMENT 'primary id',
  `message_id` varchar(40) DEFAULT NULL COMMENT 'შეტყობინების უნიკალური იდენტიფიკატორი',
  `sent_message_datetime` datetime DEFAULT NULL COMMENT 'შეტყობინების დრო როდესაც დაგენერირდა client-ის მხარეს',
  `message_type` varchar(20) DEFAULT NULL COMMENT 'შეტყობინების ტიპი',
  `message_title` text COMMENT 'შეტყობინების სათაური',
  `text` text COMMENT 'შეტყობინების ტექსტი. პრობლემის აღწერა',
  `client_ip` varchar(16) DEFAULT NULL COMMENT 'Client-ის ip მისამართი საიდანაც მოვიდა შეტყობინება',
  `client_script_name` varchar(100) DEFAULT NULL COMMENT 'client-ის სკრიპტის სახელი საიდანაც მოვიდა შეტყობინება'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `messages`
--
ALTER TABLE `messages`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `messages`
--
ALTER TABLE `messages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'primary id';
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
